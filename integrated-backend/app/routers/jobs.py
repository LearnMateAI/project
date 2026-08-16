"""
Jobs: how is that long-running thing going.

Every slow endpoint in this API answers with a job id, and this is where the client finds
out what happened to it. One record, four states:

    queued   accepted, nothing has started
    running  a worker has it; `progress.message` says what it is doing right now
    done     `result` holds the answer -- the same object the synchronous endpoint would
             have returned
    failed   `error` says why, in words meant to be shown

A poll every second or two is the intended usage. There is no long-poll and no websocket:
the work takes minutes, so the saving would be negligible against the complexity.
"""

from fastapi import APIRouter, Depends, Query

from learnmate.storage import jobs as job_store

from .. import config
from ..deps import get_current_user
from ..errors import AccessDenied, NotFound

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


def _serialize(job: dict) -> dict:
    """One job record, in the shape a client polls."""
    def stamp(key):
        value = job.get(key)
        return value.isoformat() if value else None

    return {
        "id": str(job["_id"]),
        "kind": job.get("kind"),
        "status": job.get("status"),
        "progress": job.get("progress") or {},
        "result": job.get("result"),
        "error": job.get("error"),
        "params": job.get("params", {}),
        "created_at": stamp("created_at"),
        "started_at": stamp("started_at"),
        "finished_at": stamp("finished_at"),
    }


@router.get("/{job_id}")
def get_job(job_id: str, minimal: bool = False, user: dict = Depends(get_current_user)):
    """One job's state, and its result once it is done."""
    projection = {"params": 0, "result": 0} if minimal else None
    job = job_store.get(job_id, projection=projection)
    if not job:
        raise NotFound("Job not found.")
    if str(job.get("user_id")) != str(user["id"]):
        raise AccessDenied("You do not have access to this job.")
    return _serialize(job)


@router.get("")
def list_jobs(
    status: str = Query(None, pattern="^(queued|running|done|failed)$"),
    kind: str = Query(None, pattern="^(ingest|resource|chat)$"),
    user: dict = Depends(get_current_user),
):
    """This user's recent jobs, newest first."""
    return [_serialize(job) for job in
            job_store.list_jobs(user["id"], status=status, kind=kind,
                                limit=config.MAX_JOBS)]
