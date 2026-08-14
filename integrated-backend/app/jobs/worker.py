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

`_MODEL_LOCK` is a second guard on the same rule, held for anything that touches a model.
The worker is the only consumer today, so it is uncontended; it exists so that adding a
warm-up call, a health probe that generates, or a second worker cannot quietly reintroduce
the bug.

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

logger = logging.getLogger("learnmate.api.jobs")

# Held for the duration of anything that touches a model. See the module docstring.
MODEL_LOCK = threading.Lock()

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


def _run_one(job_id: str) -> None:
    """Run one job, recording the outcome whatever happens."""
    # Imported here rather than at module scope: runners imports the services, which
    # import the engine, and the engine imports torch. Deferring it keeps `import app`
    # cheap for anything that only wants to enqueue.
    from . import runners

    job = job_store.get(job_id)
    if not job:
        logger.warning("Job %s vanished before it ran", job_id)
        return

    job_store.start(job_id)
    try:
        with MODEL_LOCK:
            result = runners.run(job)
        job_store.finish(job_id, result)
    except Exception as exc:
        # Every failure ends up on the record. A job that raised and left no trace is a
        # client polling forever, which is the one outcome worth ruling out.
        logger.exception("Job %s (%s) failed", job_id, job.get("kind"))
        job_store.fail(job_id, f"{type(exc).__name__}: {exc}")


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


def warm_up() -> None:
    """
    Pay this process's one-time costs before a user does.

    Ingesting a small PDF is about a second of real work -- extract, chunk, embed thirty-odd
    chunks -- sitting behind roughly sixteen seconds of first-use overhead: importing the
    text splitter's dependency chain (~3,900 modules, ~8s) and loading the 90 MB embedding
    model (~7s). Without this the first upload after every start absorbs all of it, and
    under `--reload` that means every time the code is touched.

    Deliberately **not** the two ~2 GB GGUFs. Those are what the lifespan docstring refuses
    to load, and rightly: they would add a minute to every restart. This loads only the
    embedding model, which ingestion and every retrieval need anyway.

    Runs on its own thread so start-up does not block on it, and takes MODEL_LOCK so it
    cannot race a job that arrives first -- an upload in the opening seconds waits for this
    load rather than starting a second one alongside it.
    """
    def _warm() -> None:
        started = time.time()
        try:
            with MODEL_LOCK:
                # Imported for the side effect: pulling the dependency chain in is the
                # point, not calling anything in it.
                from learnmate.ingestion import ingest_pdf  # noqa: F401
                from learnmate.llm.embeddings import get_embeddings

                get_embeddings().model
            logger.info("Warm-up complete in %.1fs", time.time() - started)
        except Exception:
            # Never fatal. A failed warm-up costs the first upload its old latency and
            # nothing else, so it must not take the server down with it.
            logger.warning("Warm-up failed; the first job will pay the cost instead",
                           exc_info=True)

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
