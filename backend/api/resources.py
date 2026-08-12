from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from pydantic import BaseModel
from bson import ObjectId
from bson.errors import InvalidId

from database.db import documents_collection, resources_collection
from app_infrastructure.middleware import get_current_user
from resource_generator_service.learnmate_generator import (
    TASK_NAMES, create_pending_resource, generate_resource_via_learnmate,
)

router = APIRouter(prefix="/api/resources", tags=["resources"])


class GenerateRequest(BaseModel):
    document_id: str
    resource_type: str  # one of TASK_NAMES: mcq, summary, keypoints, practice_qsn


def _verify_document_ownership(document_id: str, user_id: str):
    try:
        doc = documents_collection.find_one({"_id": ObjectId(document_id)})
    except InvalidId:
        raise HTTPException(status_code=400, detail="Invalid document id.")
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")
    if doc["owner_id"] != user_id:
        raise HTTPException(status_code=403, detail="You do not have access to this document.")
    return doc


def _serialize(r: dict) -> dict:
    return {
        "id": str(r["_id"]),
        "document_id": r["document_id"],
        "resource_type": r["resource_type"],
        "content": r["content"],
        "verification_status": r["verification_status"],
        "score": r.get("score"),
        "threshold": r.get("threshold"),
        "reasoning": r.get("reasoning"),
        "created_at": r["created_at"].isoformat(),
    }


@router.post("/generate", status_code=202)
def generate(payload: GenerateRequest, background_tasks: BackgroundTasks,
             user: dict = Depends(get_current_user)):
    if payload.resource_type not in TASK_NAMES:
        raise HTTPException(status_code=400, detail=f"resource_type must be one of {TASK_NAMES}")

    doc = _verify_document_ownership(payload.document_id, user["id"])

    if doc["processing_status"] != "Ready":
        raise HTTPException(
            status_code=400,
            detail=f"This document isn't ready yet (status: {doc['processing_status']}). Please wait for processing to finish.",
        )
    if not doc.get("learnmate_doc_id"):
        raise HTTPException(
            status_code=400,
            detail="This document was uploaded before local generation was wired in. Please re-upload it.",
        )

    resource = create_pending_resource(resources_collection, payload.document_id, payload.resource_type)
    background_tasks.add_task(
        generate_resource_via_learnmate, resources_collection, resource["id"],
        payload.resource_type, doc["learnmate_doc_id"],
    )
    return resource


@router.get("")
def list_resources(document_id: str, user: dict = Depends(get_current_user)):
    _verify_document_ownership(document_id, user["id"])
    resources = resources_collection.find({"document_id": document_id}).sort("created_at", -1)
    return [_serialize(r) for r in resources]


@router.get("/{resource_id}")
def get_resource(resource_id: str, user: dict = Depends(get_current_user)):
    try:
        r = resources_collection.find_one({"_id": ObjectId(resource_id)})
    except InvalidId:
        raise HTTPException(status_code=400, detail="Invalid resource id.")
    if not r:
        raise HTTPException(status_code=404, detail="Resource not found.")
    _verify_document_ownership(r["document_id"], user["id"])  # ownership follows the document
    return _serialize(r)
