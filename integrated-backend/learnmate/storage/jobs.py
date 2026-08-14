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
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union

from bson import ObjectId

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
           message: str = "Queued.") -> Dict:
    """Record a new job as queued and return it."""
    record = {
        "user_id": str(user_id),
        "kind": kind,
        "status": QUEUED,
        "params": params or {},
        "progress": {"message": message, "current": 0, "total": None},
        "result": None,
        "error": None,
        "created_at": datetime.now(timezone.utc),
        "started_at": None,
        "finished_at": None,
    }
    record["_id"] = _collection().insert_one(record).inserted_id
    return record


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


def finish(job_id, result: Any = None, message: str = "Done.") -> None:
    """Mark a job done, with whatever the caller should be handed back."""
    _collection().update_one(
        {"_id": coerce_id(job_id)},
        {"$set": {"status": DONE, "result": result, "error": None,
                  "finished_at": datetime.now(timezone.utc),
                  "progress.message": message,
                  # Cleared, not kept. The streamed text was the newest *attempt*; the
                  # result holds the attempt that actually won, which is not always the
                  # same one (see chat_agent/persist.best_attempt). Leaving both on the
                  # record invites a client to render the wrong one.
                  "progress.partial": None,
                  "progress.reply_ready": False}},
    )


def fail(job_id, error: str) -> None:
    """Mark a job failed, keeping the message for the user to read."""
    _collection().update_one(
        {"_id": coerce_id(job_id)},
        {"$set": {"status": FAILED, "error": str(error)[:2000],
                  "finished_at": datetime.now(timezone.utc),
                  "progress.message": "Failed."}},
    )


def fail_running(reason: str) -> int:
    """
    Fail every job left mid-flight by a stopped process. Returns how many.

    Called once at startup. The alternative -- leaving them `running` -- is a client
    polling forever for a worker that died with the process.
    """
    result = _collection().update_many(
        {"status": {"$in": [QUEUED, RUNNING]}},
        {"$set": {"status": FAILED, "error": reason,
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
