"""
The job queue's consumers: worker threads, and how many of them there may be.

    enqueue(user_id, kind, params) -> a job record, already persisted as `queued`
                |
                v
        [ queue backend ]  --> worker thread(s) --> runners.run(kind, ...) --> done/failed

Two backends (app/jobs/queue.py, chosen by JOB_QUEUE_BACKEND):

    memory   the original: an in-process queue.Queue and **one** worker thread.
    mongo    the job records are the queue; workers claim jobs under a renewable lease.
             Any number of threads here, and any number of worker processes elsewhere
             (python -m app.jobs.worker_main), share one database.

**One** worker while a model runs in this process, and this is a correctness requirement
rather than a resource one. `llama_cpp.Llama` holds a single mutable context: two threads
calling it at once interleave their tokens and corrupt both replies. Serialising also
happens to be the right resource decision on a 3B CPU model -- two concurrent generations
do not finish in half the time, they finish in twice. So JOB_WORKERS is forced to 1
whenever either model's backend is `llamacpp` (see effective_worker_count).

Served models are a different machine. llama-server with N parallel slots batches the
requests of N concurrent turns into one forward pass per token (continuous batching), so N
concurrent turns *do* finish sooner than N sequential ones -- which is the whole case for
the pool. What this process still shares between threads then is the embedding model, the
reranker and the cache verifier, and each of those guards itself where it lives:

    llm/llamacpp.py     _LLAMA_LOCK    every generation, for its whole duration
    llm/runtime.py      _LOAD_LOCK     constructing a GGUF, so it is read once and not twice
    llm/embeddings.py   _LOAD_LOCK, _ENCODE_LOCK
    llm/rerank.py       _LOAD_LOCK, _PREDICT_LOCK
    llm/equivalence.py  _LOAD_LOCK, _PREDICT_LOCK

Everything crossing the boundary is a job *record*, not an object: the API answers "is it
finished" by reading Mongo, so a poll works from any process and does not depend on this
thread's memory.
"""

import logging
import threading
import time
import uuid
from contextlib import nullcontext
from typing import Dict, List, Optional, Sequence, Tuple

from learnmate.storage import jobs as job_store
from learnmate.runtime_limits import JobTimeout, clear_deadline, set_deadline_seconds
from learnmate.storage.mongo import StorageUnavailable
from learnmate.storage.qdrant_vectors import QdrantUnavailable

from .. import config
from .queue import SHUTDOWN, make_queue

logger = logging.getLogger("learnmate.api.jobs")

_BACKEND = None
_WORKERS: List[threading.Thread] = []
_REAPER: Optional[threading.Thread] = None
_STOP = threading.Event()
_START_LOCK = threading.Lock()


def _backend(kinds: Optional[Sequence[str]] = None):
    """The configured queue backend, built once per process."""
    global _BACKEND
    if _BACKEND is None:
        _BACKEND = make_queue(config.JOB_QUEUE_BACKEND, kinds or config.JOB_KINDS,
                              config.JOB_LEASE_S, config.JOB_POLL_S)
    return _BACKEND


def enqueue(user_id: str, kind: str, params: Dict, message: str = "Queued.") -> Dict:
    """
    Record a job and hand it to the workers. Returns the record, already `queued`.

    Written to Mongo *before* it is queued, so a client that polls immediately finds a
    job rather than a 404.
    """
    backend = _backend()
    # Retries only make sense where a lease can lapse; an in-memory job dies with its
    # process either way.
    attempts = config.JOB_MAX_ATTEMPTS if backend.leases else 1
    job = job_store.create(user_id, kind, params, message=message, max_attempts=attempts)
    backend.put(str(job["_id"]))
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


def effective_worker_count(requested: int = None, generator_backend: str = None,
                           judge_backend: str = None) -> Tuple[int, Optional[str]]:
    """
    How many worker threads this process may run, and why, if fewer than asked.

    One whenever a model lives in this process (see the module docstring). Otherwise as
    many as configured -- each will mostly be waiting on an HTTP call to a model server.
    """
    from learnmate import config as engine_config

    requested = max(1, requested or config.JOB_WORKERS)
    backends = {"generator": (generator_backend or engine_config.GENERATOR_BACKEND),
                "judge": (judge_backend or engine_config.JUDGE_BACKEND)}
    in_process = sorted(role for role, backend in backends.items() if backend == "llamacpp")
    if requested > 1 and in_process:
        return 1, (f"{' and '.join(in_process)} run in-process (llamacpp); one worker. "
                   f"Serve the models (LEARNMATE_*_BACKEND=http) to run {requested}.")
    return requested, None


class _Heartbeat:
    """
    Renews a job's lease on a side thread while the job runs.

    `lost` goes up if a renewal finds the lease gone -- this worker was presumed dead
    (a stall longer than a lease) and the job requeued. Its result must then be dropped:
    another worker may already be writing the real one.
    """

    def __init__(self, job_id: str, worker_id: str, lease_s: float, every_s: float):
        self.job_id, self.worker_id = job_id, worker_id
        self.lease_s, self.every_s = lease_s, every_s
        self.lost = False
        self._stop = threading.Event()
        self._thread = None

    def _run(self) -> None:
        while not self._stop.wait(self.every_s):
            try:
                if not job_store.heartbeat(self.job_id, self.worker_id, self.lease_s):
                    self.lost = True
                    return
            except Exception:
                # A blip talking to Mongo. The lease has slack for exactly this; if the
                # outage outlasts it, the next successful renewal reports the loss.
                logger.debug("Heartbeat for %s failed", self.job_id, exc_info=True)

    def __enter__(self):
        self._thread = threading.Thread(target=self._run, daemon=True,
                                        name=f"lease-{self.job_id[-6:]}")
        self._thread.start()
        return self

    def __exit__(self, *exc) -> bool:
        self._stop.set()
        self._thread.join(timeout=5)
        return False


def _execute(job: Dict, worker_id: Optional[str] = None) -> None:
    """Run one claimed job, recording the outcome whatever happens."""
    # Imported here rather than at module scope: runners imports the services, which
    # import the engine, and the engine imports torch. Deferring it keeps `import app`
    # cheap for anything that only wants to enqueue.
    from . import runners
    from learnmate import config as engine_config

    job_id = str(job["_id"])
    lease = (_Heartbeat(job_id, worker_id, config.JOB_LEASE_S, config.JOB_HEARTBEAT_S)
             if worker_id else nullcontext())
    try:
        set_deadline_seconds(engine_config.JOB_TIMEOUT_S)
        with lease as beat:
            result = runners.run(job)
        if beat is not None and beat.lost:
            logger.warning("Job %s finished after its lease was lost; result dropped", job_id)
            return
        if not job_store.finish(job_id, result, worker_id=worker_id):
            logger.warning("Job %s: lease lost before the result was written", job_id)
    except Exception as exc:
        # Every failure ends up on the record. A job that raised and left no trace is a
        # client polling forever, which is the one outcome worth ruling out.
        logger.exception("Job %s (%s) failed", job_id, job.get("kind"))
        job_store.fail(job_id, f"{type(exc).__name__}: {exc}", _error_code(exc),
                       worker_id=worker_id)
    finally:
        clear_deadline()


def _run_one(job_id: str) -> None:
    """Run one job by id, outside any lease: the in-memory path, and scripts."""
    job = job_store.get(job_id)
    if not job:
        logger.warning("Job %s vanished before it ran", job_id)
        return
    job_store.start(job_id)
    _execute(job)


def _loop(worker_id: str) -> None:
    """Take jobs until told to stop."""
    backend = _backend()
    while not _STOP.is_set():
        try:
            job = backend.take(worker_id, timeout=1.0)
        except Exception:
            # Mongo unreachable, typically. Back off rather than spin.
            logger.warning("Worker %s could not take a job", worker_id, exc_info=True)
            _STOP.wait(2.0)
            continue
        if job is SHUTDOWN:
            break
        if job is None:
            continue
        _execute(job, worker_id if backend.leases else None)


def _reap_loop() -> None:
    """Requeue jobs whose worker stopped renewing; expire old cache entries while at it."""
    from learnmate import config as engine_config

    ticks = 0
    while not _STOP.wait(config.JOB_REAP_INTERVAL_S):
        ticks += 1
        try:
            requeued, failed = job_store.requeue_expired(config.JOB_RETRY_BACKOFF_S)
            if requeued or failed:
                logger.warning("Lapsed leases: %d job(s) requeued, %d failed", requeued, failed)
        except Exception:
            logger.debug("Reaper pass failed", exc_info=True)
        if engine_config.CACHE_ENABLED and ticks % 40 == 0:
            try:
                from learnmate.cache import get_answer_cache

                get_answer_cache().purge_expired()
            except Exception:
                logger.debug("Cache purge failed", exc_info=True)


def start_workers(count: int = None, kinds: Optional[Sequence[str]] = None,
                  name: str = None) -> int:
    """
    Start this process's workers (and, under the lease queue, the reaper). Returns how many.

    Idempotent: a second call while workers are alive does nothing.
    """
    global _REAPER
    with _START_LOCK:
        if any(thread.is_alive() for thread in _WORKERS):
            return len(_WORKERS)

        backend = _backend(kinds)
        stale = backend.startup()
        if stale:
            logger.info("Failed %d job(s) left behind by a previous process", stale)

        count, reason = effective_worker_count(count)
        if reason:
            logger.warning(reason)
        prefix = name or f"w-{uuid.uuid4().hex[:6]}"

        _STOP.clear()
        _WORKERS.clear()
        for index in range(count):
            worker_id = f"{prefix}-{index}"
            thread = threading.Thread(target=_loop, args=(worker_id,), daemon=True,
                                      name=f"learnmate-worker-{index}")
            thread.start()
            _WORKERS.append(thread)

        if backend.leases and (_REAPER is None or not _REAPER.is_alive()):
            _REAPER = threading.Thread(target=_reap_loop, daemon=True,
                                       name="learnmate-reaper")
            _REAPER.start()

        logger.info("Job workers started: %d x %s queue (kinds: %s)", count, backend.name,
                    ", ".join(getattr(backend, "kinds", None) or config.JOB_KINDS))
        return count


def start_worker() -> None:
    """
    The API process's entry point (server.py lifespan).

    Under the lease queue with JOB_RUN_IN_API=0 the API only enqueues and the work runs in
    worker_main processes. The in-memory queue has no such option -- nothing outside this
    process can see it -- so it always starts its worker here.
    """
    backend = _backend()
    if backend.leases and not config.JOB_RUN_IN_API:
        stale = backend.startup()
        if stale:
            logger.info("Failed %d orphaned job(s)", stale)
        logger.info("JOB_RUN_IN_API=0: this process enqueues; worker_main processes run jobs")
        return
    start_workers()


def worker_status() -> Dict:
    """For /api/health: which queue, how many workers here, and how deep it is."""
    backend = _backend()
    status = {"backend": backend.name,
              "workers_here": sum(1 for thread in _WORKERS if thread.is_alive())}
    try:
        status.update(job_store.queue_depth())
    except Exception as exc:
        status["error"] = str(exc)
    return status


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

        if config.CACHE_ENABLED:
            # Cached questions embedded by another model can never match again; free them.
            from learnmate.cache import get_answer_cache

            get_answer_cache().purge_embedding_mismatch()

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
    Stop the workers at shutdown.

    A job already running is given `timeout` to finish; past that its thread is left to die
    with the process. Under the in-memory queue the next start fails its record; under the
    lease queue its lease lapses and another worker picks it up again. Waiting indefinitely
    would hang the server on a generation that had minutes left to run.
    """
    _STOP.set()
    if _BACKEND is not None:
        _BACKEND.wake_all(len(_WORKERS))
    deadline = time.monotonic() + timeout
    for thread in list(_WORKERS):
        thread.join(timeout=max(0.0, deadline - time.monotonic()))
    _WORKERS.clear()
    logger.info("Job workers stopped")
