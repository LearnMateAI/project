"""
Background work, as records.

    {_id, user_id, kind, status, params, progress, result, error, timestamps}

Everything slow in this system runs here rather than inside a request: ingesting a PDF is
a few thousand embeddings, a chat turn is ~30 seconds of local inference, and a
whole-document question set is minutes. A browser will not hold a connection that long,
and a proxy certainly will not.

    queued -> running -+-> done
                       |
                       +-> failed

The record is the API's answer to "is it finished yet", so it is written at every
transition and carries `progress` for the ones that take long enough to want a number.
The queue itself -- one worker, in-process -- is app/jobs/worker.py; this module only
stores what that worker is doing.

A job that was `running` when the process died is not recoverable: the work was in memory.
`fail_running()` is called once at startup to mark those, so a poll gets an answer instead
of waiting on a worker that no longer exists.

That is the in-memory queue's rule. With JOB_QUEUE_BACKEND=mongo the records *are* the
queue, and a job carries a lease instead:

    queued --claim()--> running (lease_owner, lease_until) --finish()/fail()--> done | failed
                           |   ^
                           |   +-- heartbeat() renews lease_until while the worker lives
                           +-- lease lapses (worker died) --requeue_expired()--> queued again,
                               or failed once max_attempts runs have been spent

Claiming is one atomic find_one_and_update, so two workers can never take the same job,
and every lease time is computed by the database server (`$$NOW`), so workers on machines
with different clocks still agree on when a lease has lapsed.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

from bson import ObjectId
from pymongo import ReturnDocument

from .. import config
from .ids import coerce_id
from .mongo import get_db

QUEUED = "queued"
RUNNING = "running"
DONE = "done"
FAILED = "failed"


def _collection():
    return get_db()[config.COLL_JOBS]


def create(user_id: str, kind: str, params: Optional[Dict] = None,
           message: str = "Queued.", max_attempts: int = 1) -> Dict:
    """Record a new job as queued and return it."""
    now = datetime.now(timezone.utc)
    record = {
        "user_id": str(user_id),
        "kind": kind,
        "status": QUEUED,
        "params": params or {},
        "progress": {"message": message, "current": 0, "total": None},
        "result": None,
        "error": None,
        "error_code": None,
        "created_at": now,
        "started_at": None,
        "finished_at": None,
        # Lease-queue bookkeeping. Inert under the in-memory queue.
        "available_at": now,
        "attempts": 0,
        "max_attempts": max(1, int(max_attempts)),
        "lease_owner": None,
        "lease_until": None,
        "heartbeat_at": None,
    }
    record["_id"] = _collection().insert_one(record).inserted_id
    return record


def _lease_expiry(lease_s: float) -> Dict:
    """`$$NOW + lease_s`, evaluated by the database server."""
    return {"$dateAdd": {"startDate": "$$NOW", "unit": "millisecond",
                         "amount": int(lease_s * 1000)}}


def claim(worker_id: str, kinds: Sequence[str], lease_s: float) -> Optional[Dict]:
    """
    Atomically take the oldest due job of one of `kinds`, or None if there is none.

    The update is an aggregation pipeline so the lease is stamped with the server's clock.
    `available_at` is compared with this process's clock, which only decides *when* a
    backed-off retry becomes eligible -- a few milliseconds of skew there is harmless.
    """
    return _collection().find_one_and_update(
        {"status": QUEUED, "kind": {"$in": list(kinds)},
         "available_at": {"$lte": datetime.now(timezone.utc)}},
        [{"$set": {
            "status": RUNNING,
            "lease_owner": worker_id,
            "started_at": "$$NOW",
            "heartbeat_at": "$$NOW",
            "lease_until": _lease_expiry(lease_s),
            "attempts": {"$add": [{"$ifNull": ["$attempts", 0]}, 1]},
            "progress.message": "Started.",
        }}],
        sort=[("created_at", 1)],
        return_document=ReturnDocument.AFTER,
    )


def heartbeat(job_id, worker_id: str, lease_s: float) -> bool:
    """
    Renew a lease. False means this worker no longer holds it -- the job was reaped and
    may already be running elsewhere -- and whatever it produces must be thrown away.
    """
    result = _collection().update_one(
        {"_id": coerce_id(job_id), "status": RUNNING, "lease_owner": worker_id},
        [{"$set": {"heartbeat_at": "$$NOW", "lease_until": _lease_expiry(lease_s)}}],
    )
    return result.matched_count == 1


def requeue_expired(backoff_s: float = 0) -> Tuple[int, int]:
    """
    Recover jobs whose worker stopped renewing its lease. Returns (requeued, failed).

    Both updates are conditional on the lease still being lapsed, so any number of reapers
    can run at once and a job is moved exactly once. A job that has used its attempts is
    failed rather than tried again: a document that crashes the worker every time must
    not take down every worker in turn.
    """
    lapsed = {"$lt": ["$lease_until", "$$NOW"]}
    spent = {"$gte": [{"$ifNull": ["$attempts", 1]}, {"$ifNull": ["$max_attempts", 1]}]}
    base = {"status": RUNNING, "lease_owner": {"$ne": None}}

    failed = _collection().update_many(
        {**base, "$expr": {"$and": [lapsed, spent]}},
        [{"$set": {"status": FAILED, "error_code": "interrupted",
                   "error": "The worker running this job stopped responding, and it has "
                            "used all its attempts. Please try again.",
                   "finished_at": "$$NOW", "lease_owner": None, "lease_until": None,
                   "progress.message": "Failed."}}],
    ).modified_count

    requeued = _collection().update_many(
        {**base, "$expr": {"$and": [lapsed, {"$not": [spent]}]}},
        [{"$set": {"status": QUEUED, "lease_owner": None, "lease_until": None,
                   "available_at": {"$dateAdd": {"startDate": "$$NOW", "unit": "millisecond",
                                                 "amount": int(backoff_s * 1000)}},
                   "progress.message": "Retrying: the worker running this stopped.",
                   "progress.partial": None, "progress.reply_ready": False}}],
    ).modified_count
    return requeued, failed


def fail_legacy_orphans(reason: str) -> int:
    """
    At start-up under the lease queue: fail `running` jobs that carry no lease.

    Those were taken by an in-memory worker in a process that has since stopped -- no lease
    will ever lapse for them. Queued jobs from that era are kept, and made claimable.
    """
    now = datetime.now(timezone.utc)
    _collection().update_many(
        {"status": QUEUED, "available_at": {"$exists": False}},
        {"$set": {"available_at": now, "attempts": 0, "max_attempts": 1}})
    return _collection().update_many(
        {"status": RUNNING, "lease_owner": {"$in": [None]}},
        {"$set": {"status": FAILED, "error": reason, "error_code": "interrupted",
                  "finished_at": now, "progress.message": "Failed."}},
    ).modified_count


def queue_depth(kinds: Optional[Sequence[str]] = None) -> Dict[str, int]:
    """How many jobs are waiting and running -- the health endpoint's queue gauge."""
    match: Dict[str, Any] = {"status": {"$in": [QUEUED, RUNNING]}}
    if kinds:
        match["kind"] = {"$in": list(kinds)}
    counts = {row["_id"]: row["n"] for row in _collection().aggregate([
        {"$match": match}, {"$group": {"_id": "$status", "n": {"$sum": 1}}}])}
    return {"queued": counts.get(QUEUED, 0), "running": counts.get(RUNNING, 0)}


def start(job_id, message: str = "Started.") -> None:
    """Mark a job as running."""
    _collection().update_one(
        {"_id": coerce_id(job_id)},
        {"$set": {"status": RUNNING, "started_at": datetime.now(timezone.utc),
                  "progress.message": message}},
    )


def set_progress(job_id, message: str, current: int = None, total: int = None) -> None:
    """
    Update what a running job is doing.

    Never raises: progress is a courtesy to whoever is watching, and a failed write here
    must not be able to take down the work itself.
    """
    update: Dict[str, Any] = {"progress.message": message}
    if current is not None:
        update["progress.current"] = current
    if total is not None:
        update["progress.total"] = total
    try:
        _collection().update_one({"_id": coerce_id(job_id)}, {"$set": update})
    except Exception:
        pass


def set_partial(job_id, text: str) -> None:
    """
    Update the answer a running job has produced so far.

    Separate from `set_progress` because the two say different things and a client renders
    them differently: `progress.message` is commentary that replaces the line before it
    ("Evaluating..."), `progress.partial` is the reply itself, growing. Sharing one field
    would mean the answer flickering away every time a node logged something.

    The caller is expected to throttle -- this is one Mongo write per call and a 3B model
    emits several tokens a second. See the reporter in app/jobs/runners.py.

    Never raises, for the same reason set_progress does not: a client watching is a
    courtesy, and the generation must outlive it.
    """
    try:
        _collection().update_one({"_id": coerce_id(job_id)},
                                 {"$set": {"progress.partial": text}})
    except Exception:
        pass


def set_reply_ready(job_id, text: str) -> None:
    """
    Publish a complete answer on a job that is still running.

    The turn is not over -- the judge has yet to read this, and may force a regeneration --
    but the text is whole, and on the local models everything still to come takes longer
    than the writing did. Setting both fields in one update matters: written separately, a
    poll landing between them would find the flag on and the old partial text under it.

    `partial` keeps its meaning of "the newest text there is"; `reply_ready` is the client's
    licence to render it as an answer rather than as something mid-flight. A job that
    finishes clears both -- see finish(), and the note there about which text actually won.
    """
    try:
        _collection().update_one(
            {"_id": coerce_id(job_id)},
            {"$set": {"progress.partial": text, "progress.reply_ready": True}},
        )
    except Exception:
        pass


def _owned(job_id, worker_id: Optional[str]) -> Dict:
    """The filter for a terminal write: under a lease, only by the worker holding it."""
    query: Dict[str, Any] = {"_id": coerce_id(job_id)}
    if worker_id is not None:
        query.update({"status": RUNNING, "lease_owner": worker_id})
    return query


def finish(job_id, result: Any = None, message: str = "Done.",
           worker_id: Optional[str] = None) -> bool:
    """
    Mark a job done, with whatever the caller should be handed back.

    With a `worker_id`, only if that worker still holds the lease; False means it lost the
    lease (it was presumed dead and the job requeued) and this result is discarded.
    """
    update: Dict[str, Any] = {
        "status": DONE, "result": result, "error": None, "error_code": None,
        "finished_at": datetime.now(timezone.utc),
        "progress.message": message,
        # Cleared, not kept. The streamed text was the newest *attempt*; the
        # result holds the attempt that actually won, which is not always the
        # same one (see chat_agent/persist.best_attempt). Leaving both on the
        # record invites a client to render the wrong one.
        "progress.partial": None,
        "progress.reply_ready": False,
    }
    if isinstance(result, dict) and result.get("timings"):
        update["progress.timings"] = result["timings"]
    if worker_id is not None:
        update["lease_owner"] = None
        update["lease_until"] = None
    return _collection().update_one(_owned(job_id, worker_id),
                                    {"$set": update}).matched_count == 1


def fail(job_id, error: str, error_code: str = "unknown",
         worker_id: Optional[str] = None) -> bool:
    """Mark a job failed, keeping the message for the user to read."""
    update: Dict[str, Any] = {"status": FAILED, "error": str(error)[:2000],
                              "error_code": error_code,
                              "finished_at": datetime.now(timezone.utc),
                              "progress.message": "Failed."}
    if worker_id is not None:
        update["lease_owner"] = None
        update["lease_until"] = None
    return _collection().update_one(_owned(job_id, worker_id),
                                    {"$set": update}).matched_count == 1


def fail_running(reason: str) -> int:
    """
    Fail every job left mid-flight by a stopped process. Returns how many.

    Called once at startup. The alternative -- leaving them `running` -- is a client
    polling forever for a worker that died with the process.
    """
    result = _collection().update_many(
        {"status": {"$in": [QUEUED, RUNNING]}},
        {"$set": {"status": FAILED, "error": reason, "error_code": "interrupted",
                  "finished_at": datetime.now(timezone.utc),
                  "progress.message": "Failed."}},
    )
    return result.modified_count


def get(job_id: Union[str, ObjectId], projection: Optional[Dict] = None) -> Optional[Dict]:
    """One job by id."""
    oid = coerce_id(job_id)
    if oid is None:
        return None
    return _collection().find_one({"_id": oid}, projection=projection)


def list_jobs(user_id: str, status: str = None, kind: str = None,
              limit: int = 25) -> List[Dict]:
    """One user's jobs, newest first."""
    query: Dict[str, Any] = {"user_id": str(user_id)}
    if status:
        query["status"] = status
    if kind:
        query["kind"] = kind
    return list(_collection().find(query).sort("created_at", -1).limit(limit))
