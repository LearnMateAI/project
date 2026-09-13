"""
Study material: generate it, read it back.

Generation returns **202 with a job id**. On the default local backend a single passage of
five MCQs is roughly a minute -- generate, structurally validate, judge, and regenerate
once if the judge rejected it -- and forty questions across a whole book is several. The
client polls `GET /api/jobs/{job_id}`; the finished job's `result` is the same object
`GET /api/resources/{id}` returns.

Four types, and two scopes:

    mcq | practice_qsn | keypoints | summary
    scope=passage   one extract, optionally the pages most relevant to `topic`
    scope=document  the whole PDF, read in groups and pooled (folded, for a summary)

`summary` and `key_points` are still accepted as type names so the existing frontend keeps
working while it is updated.
"""

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response

from ..deps import get_current_user
from ..jobs import enqueue
from ..schemas import GenerateRequest
from ..services import export as export_service
from ..services import ownership as access
from ..services import resources as service

router = APIRouter(prefix="/api/resources", tags=["resources"])


@router.post("/generate", status_code=202)
def generate(payload: GenerateRequest, user: dict = Depends(get_current_user)):
    """
    Queue one generation run.

    Validated before queueing -- an unknown resource type, a document that is not this
    user's, or one still processing all fail here rather than a minute later on the
    worker.
    """
    task = service.resolve_task(payload.resource_type)
    # Raises if the document is not this user's or is not Ready yet.
    access.require_ready_document(user["id"], payload.document_id)

    job = enqueue(
        user["id"], "resource",
        {
            "document_id": payload.document_id,
            "resource_type": task,
            "scope": payload.scope,
            "topic": payload.topic,
            "pages": payload.pages,
            "count": payload.count,
            "per_page": payload.per_page,
            "evaluate": payload.evaluate,
            "threshold": payload.threshold,
            "summary_style": payload.summary_style,
            "difficulty": payload.difficulty,
            "model_id": payload.model_id,
        },
        message=f"Waiting to generate {task}.",
    )

    return {"job_id": str(job["_id"]), "status": job["status"], "kind": "resource"}


@router.get("")
def list_resources(
    document_id: str = Query(None),
    resource_type: str = Query(None),
    user: dict = Depends(get_current_user),
):
    """This user's generated resources, newest first."""
    return service.list_resources(user["id"], document_id, resource_type)


@router.get("/{resource_id}")
def get_resource(resource_id: str, user: dict = Depends(get_current_user)):
    """
    One resource, with its whole attempt trail.

    The trail is what makes a disappointing result answerable: which gate rejected the
    first attempt, what the judge objected to, and what the retry changed.
    """
    return service.get_resource(user["id"], resource_id)


@router.get("/{resource_id}/export")
def export_resource(
    resource_id: str,
    format: str = Query("docx", pattern="^(docx|pptx)$"),
    user: dict = Depends(get_current_user),
):
    """
    Download a stored resource as Word or PowerPoint.

    Formats the judged content already in Mongo. Does not generate or re-judge.
    """
    data, media_type, filename = export_service.export_resource(
        user["id"], resource_id, format)
    return Response(
        content=data,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.delete("/{resource_id}")
def delete_resource(resource_id: str, user: dict = Depends(get_current_user)):
    """Delete one of this user's resources."""
    return service.delete_resource(user["id"], resource_id)
