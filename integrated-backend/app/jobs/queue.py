"""
Where queued jobs wait: two interchangeable backends behind one small interface.

    memory   queue.Queue in this process. The original design: exactly one consumer, and
             a job exists only while this process does -- a restart fails whatever was
             queued or running, because that work lived in memory.

    mongo    the `jobs` collection is the queue. Any number of worker threads, in any
             number of processes on any number of machines, claim jobs atomically and hold
             them under a lease they keep renewing (see learnmate/storage/jobs.py). A worker
             that dies stops renewing; its job goes back in the queue when the lease lapses.

MongoDB here is a standalone server, not a replica set, so there are no change streams to
push new jobs to workers. They poll -- one indexed query per idle interval -- and a job
enqueued by this same process wakes its own workers immediately through an Event.
"""

import queue
import threading
from typing import Dict, Optional, Sequence

from learnmate.storage import jobs as job_store

# Returned by take() when the worker should exit.
SHUTDOWN = object()


class MemoryQueue:
    name = "memory"
    # Jobs are not leased: a record is `running` exactly while this process runs it.
    leases = False

    def __init__(self):
        self._queue: "queue.Queue[Optional[str]]" = queue.Queue()

    def startup(self) -> int:
        """Fail whatever the last process left queued or running -- that work was in memory."""
        return job_store.fail_running("Interrupted by a server restart. Please try again.")

    def put(self, job_id: str) -> None:
        self._queue.put(job_id)

    def take(self, worker_id: str, timeout: float):
        try:
            job_id = self._queue.get(timeout=timeout)
        except queue.Empty:
            return None
        if job_id is None:
            return SHUTDOWN
        job = job_store.get(job_id)
        if job is None:
            return None
        job_store.start(job_id)
        return job

    def wake_all(self, workers: int) -> None:
        for _ in range(max(1, workers)):
            self._queue.put(None)


class MongoLeaseQueue:
    name = "mongo"
    leases = True

    def __init__(self, kinds: Sequence[str], lease_s: float, poll_s: float):
        self.kinds = list(kinds)
        self.lease_s = lease_s
        self.poll_s = poll_s
        self._wake = threading.Event()
        self._stopping = False

    def startup(self) -> int:
        """
        Fail jobs an in-memory worker left running, and nothing else.

        Deliberately *not* fail_running(): other processes' workers may be mid-job right
        now, and their leases -- not this process starting -- decide whether they are alive.
        """
        return job_store.fail_legacy_orphans(
            "Interrupted by a server restart. Please try again.")

    def put(self, job_id: str) -> None:
        self._wake.set()

    def take(self, worker_id: str, timeout: float):
        if self._stopping:
            return SHUTDOWN
        job = job_store.claim(worker_id, self.kinds, self.lease_s)
        if job is not None:
            return job
        # Nothing due. Sleep until this process enqueues something, or the poll interval
        # passes and another process's enqueue might be waiting.
        self._wake.wait(timeout=min(timeout, self.poll_s))
        self._wake.clear()
        return SHUTDOWN if self._stopping else None

    def wake_all(self, workers: int) -> None:
        self._stopping = True
        self._wake.set()


def make_queue(backend: str, kinds: Sequence[str], lease_s: float, poll_s: float):
    backend = (backend or "memory").lower()
    if backend == "mongo":
        return MongoLeaseQueue(kinds, lease_s, poll_s)
    if backend == "memory":
        return MemoryQueue()
    raise ValueError(f"Unknown JOB_QUEUE_BACKEND {backend!r}; expected 'memory' or 'mongo'.")


def describe(backend) -> Dict:
    return {"backend": backend.name, "leases": backend.leases}
