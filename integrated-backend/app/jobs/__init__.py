"""
Background work.

Everything slow in this system runs here rather than inside a request. On the default
local backend a chat turn is ~30-60 seconds, ingesting a book is a few thousand embeddings,
and forty MCQs across a whole document is several minutes -- none of which a browser will
hold a connection for, and none of which a proxy will allow it to.

    POST /api/...            -> 202 {job_id}
    GET  /api/jobs/{job_id}  -> queued | running | done | failed, with progress

    worker.py   the queue: one thread, and why it is exactly one
    runners.py  what each kind of job actually does

The job *records* live in learnmate/storage/jobs.py, next to the rest of the persistence.
"""

from .worker import enqueue, shutdown, start_worker

__all__ = ["enqueue", "shutdown", "start_worker"]
