"""
The job queue: one worker thread, and why exactly one.

    enqueue(user_id, kind, params) -> a job record, already persisted as `queued`
                |
                v
        [ queue.Queue ]  --> the worker thread --> runners.run(kind, ...) --> done/failed

**One** worker, not a pool, and this is a correctness requirement rather than a resource
one. `llama_cpp.Llama` holds a single mutable context: two threads calling it at once
interleave their tokens and corrupt both replies. Sentence-transformers has the same
problem under torch's default threading. A `ThreadPoolExecutor(max_workers=4)` here would
produce answers that are subtly wrong rather than an error you could find.

Serialising also happens to be the right resource decision on a 3B CPU model -- two
concurrent generations do not finish in half the time, they finish in twice -- but the
lock would be needed even if it did not.

The locks that enforce that rule no longer live here. This module used to hold one for the
whole of every job, which also blocked the warm-up thread behind a job's database and
network work for no reason. They now sit next to the things they protect, which is both
narrower and harder to forget:

    llm/llamacpp.py   _LLAMA_LOCK  every generation, for its whole duration
    llm/runtime.py    _LOAD_LOCK   constructing a GGUF, so it is read once and not twice
    llm/embeddings.py _LOAD_LOCK   the same, for the sentence-transformers model
    llm/rerank.py     _LOAD_LOCK   the same, for the cross-encoder

That matters because this process has two threads that touch models: this worker, and the
warm-up thread started at boot (see warm_up below). They can now overlap, so anything they
share has to be guarded where it lives rather than by whoever happens to call it.

Everything crossing the boundary is a job *record*, not an object: the API answers "is it
finished" by reading Mongo, so a poll works from any process and does not depend on this
thread's memory.
"""

import logging
import queue
import threading
import time
from typing import Dict, Optional

from learnmate.storage import jobs as job_store
from learnmate.runtime_limits import JobTimeout, clear_deadline, set_deadline_seconds
from learnmate.storage.mongo import StorageUnavailable
from learnmate.storage.qdrant_vectors import QdrantUnavailable

from .. import config

logger = logging.getLogger("learnmate.api.jobs")

_QUEUE: "queue.Queue[Optional[str]]" = queue.Queue()
_WORKER: Optional[threading.Thread] = None
_STOP = threading.Event()

# The sentinel that wakes the worker for a clean exit.
_SHUTDOWN = None


def enqueue(user_id: str, kind: str, params: Dict, message: str = "Queued.") -> Dict:
    """
    Record a job and hand it to the worker. Returns the record, already `queued`.

    Written to Mongo *before* it is queued, so a client that polls immediately finds a
    job rather than a 404.
    """
    job = job_store.create(user_id, kind, params, message=message)
    _QUEUE.put(str(job["_id"]))
    return job


def _error_code(exc: Exception) -> str:
    """Map an exception onto the codes the frontend branches on."""
    if isinstance(exc, JobTimeout):
        return "timeout"
    if isinstance(exc, (StorageUnavailable, QdrantUnavailable)):
        return "storage"
    name = type(exc).__name__.lower()
    message = str(exc).lower()
    if "timeout" in name:
        return "timeout"
    if any(word in message for word in ("gguf", "llama", "registry", "model_id",
                                        "unknown model", "could not load")):
        return "model"
    if "parse" in name or "json" in name:
        return "parse"
    if isinstance(exc, ValueError) and "model" in message:
        return "model"
    return "unknown"


def _run_one(job_id: str) -> None:
    """Run one job, recording the outcome whatever happens."""
    # Imported here rather than at module scope: runners imports the services, which
    # import the engine, and the engine imports torch. Deferring it keeps `import app`
    # cheap for anything that only wants to enqueue.
    from . import runners
    from learnmate import config as engine_config

    job = job_store.get(job_id)
    if not job:
        logger.warning("Job %s vanished before it ran", job_id)
        return

    job_store.start(job_id)
    try:
        set_deadline_seconds(engine_config.JOB_TIMEOUT_S)
        result = runners.run(job)
        job_store.finish(job_id, result)
    except Exception as exc:
        # Every failure ends up on the record. A job that raised and left no trace is a
        # client polling forever, which is the one outcome worth ruling out.
        logger.exception("Job %s (%s) failed", job_id, job.get("kind"))
        job_store.fail(job_id, f"{type(exc).__name__}: {exc}", _error_code(exc))
    finally:
        clear_deadline()


def _loop() -> None:
    """Take jobs off the queue until told to stop."""
    while not _STOP.is_set():
        try:
            job_id = _QUEUE.get(timeout=1.0)
        except queue.Empty:
            continue

        if job_id is _SHUTDOWN:
            _QUEUE.task_done()
            break

        try:
            _run_one(job_id)
        finally:
            _QUEUE.task_done()


def start_worker() -> None:
    """
    Start the worker, and fail any job the last process left mid-flight.

    Those jobs are unrecoverable -- the queue and the work both lived in the dead
    process's memory -- so they are marked failed rather than left `running` for a client
    to poll forever against a worker that no longer exists.

    This assumes **one server process per database**, which is also what the single
    worker assumes. Starting a second server against the same MongoDB would have it fail
    the first server's in-flight jobs on the way up. Running more than one would mean
    moving the queue out of process memory -- a real broker, or a Mongo-backed claim with
    a lease -- which is a larger change than it looks and is not needed at this scale.
    """
    global _WORKER

    if _WORKER is not None and _WORKER.is_alive():
        return

    stale = job_store.fail_running("Interrupted by a server restart. Please try again.")
    if stale:
        logger.info("Failed %d job(s) left running by a previous process", stale)

    _STOP.clear()
    _WORKER = threading.Thread(target=_loop, name="learnmate-worker", daemon=True)
    _WORKER.start()
    logger.info("Job worker started")


def _check_embedding_model() -> None:
    """
    Warn when documents on disk were embedded by a different model than is configured now.

    This is the one configuration mistake in this system that produces no error at all.
    Vectors from two different embedding models have the same shape and the same dtype;
    comparing them returns confident numbers that mean nothing, so retrieval quietly
    starts answering from general knowledge -- or worse, grounds replies on whichever
    chunks happened to land near the query in the wrong space. Nothing about that looks
    like a failure from the outside.

    A warning rather than a refusal: the fix is to re-ingest, which is minutes of work, and
    a server that will not start is a worse answer than one that says what is wrong.
    """
    try:
        from learnmate import config
        from learnmate.storage import pdf_store

        stale = pdf_store.stale_embeddings()
        if not stale:
            return

        models = sorted({row.get("embedding_model") for row in stale})
        logger.warning(
            "%d document(s) were embedded with %s but LEARNMATE_EMBEDDING_MODEL is now %r. "
            "Their vectors are not comparable to queries embedded by the new model and "
            "retrieval will be wrong. Re-ingest them (force=True), or set the setting back. "
            "Affected: %s",
            len(stale), ", ".join(repr(name) for name in models), config.EMBEDDING_MODEL,
            ", ".join(row.get("filename", "?") for row in stale[:5]),
        )
    except Exception:
        # A check that cannot run must not be the reason a server fails to start.
        logger.debug("Embedding-model check skipped", exc_info=True)


def _warm_models() -> None:
    """
    Load the generator and the judge, and push one token through each.

    A token, rather than only opening the files, because construction is not the whole of
    the first call's cost: the KV cache is allocated, the chat template is resolved, and on
    Metal the shaders are compiled, on a model's first *generation*. Loading without
    generating would move about half the cliff and leave the rest on the first question.

    Only llama.cpp models are warmed. An `http` endpoint is somebody else's process to warm,
    and a dummy Gemini call would spend quota to save nothing local.

    The probe goes through the same no-argument accessors the agents use, so it warms the
    exact cache entries they will ask for -- see llm/registry.py, which keys wrappers by
    role and sampling settings over a single set of weights.
    """
    from langchain_core.messages import HumanMessage

    from learnmate import config as engine_config
    from learnmate.evaluator.verdict import VERDICT_SCHEMA
    from learnmate.llm import get_generator_llm, get_judge_llm

    probe = [HumanMessage(content="Hello.")]

    if engine_config.GENERATOR_BACKEND == "llamacpp":
        started = time.time()
        get_generator_llm().invoke(probe, max_tokens=1, temperature=0.0)
        logger.info("Generator ready in %.1fs (%s)",
                    time.time() - started, engine_config.GENERATOR_MODEL)

    if engine_config.JUDGE_BACKEND == "llamacpp":
        started = time.time()
        # With the schema, so the JSON grammar is compiled here as well. Every verdict is
        # decoded through it, and compiling it is part of what the first one pays for.
        get_judge_llm().invoke(probe, max_tokens=1, response_schema=VERDICT_SCHEMA)
        logger.info("Judge ready in %.1fs (%s)",
                    time.time() - started, engine_config.JUDGE_MODEL)


def warm_up() -> None:
    """
    Pay this process's one-time costs before a user does.

    Two phases, separately switched, because they are very different bargains.

    The first is the embedding model and the ingestion import chain, and it is on by
    default. Ingesting a small PDF is about a second of real work -- extract, chunk, embed
    thirty-odd chunks -- sitting behind roughly sixteen seconds of first-use overhead:
    importing the text splitter's dependency chain (~3,900 modules, ~8s) and loading the
    90 MB embedding model (~7s). Without this the first upload after every start absorbs all
    of it, and under `--reload` that means every time the code is touched.

    The second is the two ~2 GB GGUFs, and it is off by default -- this is what the lifespan
    docstring means by refusing to load them. In development that refusal is right: four
    gigabytes at every restart makes `--reload` unusable. On the demo machine it is wrong,
    because the cost does not disappear, it just moves onto the first question somebody
    asks. API_WARM_MODELS=1 pays it at boot instead.

    Runs on its own thread, so start-up does not block on it and a job arriving in the
    opening seconds is free to proceed alongside it rather than queueing behind four
    gigabytes of loading.

    That overlap is the reason the load caches guard themselves: this thread and the worker
    can want the same model at the same moment, and whichever gets there first must be the
    only one that reads it off disk. See the module docstring for where those locks are.
    """
    if not (config.WARM_UP_ON_START or config.WARM_MODELS_ON_START):
        return

    def _warm() -> None:
        if config.WARM_UP_ON_START:
            started = time.time()
            try:
                # Imported for the side effect: pulling the dependency chain in is the
                # point, not calling anything in it.
                from learnmate.ingestion import ingest_pdf  # noqa: F401
                from learnmate.llm import rerank
                from learnmate.llm.embeddings import get_embeddings

                get_embeddings().model
                # ~90 MB, and every chat turn goes through it. Loading it here rather
                # than on the first question keeps it off the path a user is waiting on.
                rerank.available()
                logger.info("Warm-up complete in %.1fs", time.time() - started)
            except Exception:
                # Never fatal. A failed warm-up costs the first upload its old latency and
                # nothing else, so it must not take the server down with it.
                logger.warning("Warm-up failed; the first job will pay the cost instead",
                               exc_info=True)

        if config.WARM_MODELS_ON_START:
            started = time.time()
            try:
                _warm_models()
                logger.info("Models warm in %.1fs", time.time() - started)
            except Exception:
                # Same rule as above, and it matters more here: a missing GGUF downloads on
                # first use, and that download failing at boot must not stop a server whose
                # other half works.
                logger.warning("Model warm-up failed; the first turn will pay the cost "
                               "instead", exc_info=True)

        # Last, and outside both phases: this warns about a corpus embedded by a different
        # model than is configured now, which is worth saying whichever phase ran and is
        # not warming at all. It only needs Mongo.
        _check_embedding_model()

    threading.Thread(target=_warm, name="learnmate-warmup", daemon=True).start()


def shutdown(timeout: float = 5.0) -> None:
    """
    Stop the worker at shutdown.

    A job already running is given `timeout` to finish; past that the thread is left to
    die with the process, and its record is failed by the next start_worker(). Waiting
    indefinitely would hang the server on a generation that had minutes left to run.
    """
    global _WORKER

    _STOP.set()
    _QUEUE.put(_SHUTDOWN)
    if _WORKER is not None:
        _WORKER.join(timeout=timeout)
        _WORKER = None
    logger.info("Job worker stopped")
