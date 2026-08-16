from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from bson import ObjectId
from bson.errors import InvalidId

from database.db import documents_collection, chunks_collection, resources_collection
from app_infrastructure.middleware import get_current_user
from resource_generator_service.generator import generate_resource

router = APIRouter(prefix="/api/resources", tags=["resources"])


class GenerateRequest(BaseModel):
    document_id: str
    resource_type: str  # "summary" or "key_points" for now


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


@router.post("/generate", status_code=201)
def generate(payload: GenerateRequest, user: dict = Depends(get_current_user)):
    doc = _verify_document_ownership(payload.document_id, user["id"])

    if doc["processing_status"] != "Ready":
        raise HTTPException(
            status_code=400,
            detail=f"This document isn't ready yet (status: {doc['processing_status']}). Please wait for processing to finish.",
        )

    try:
        resource = generate_resource(
            chunks_collection, resources_collection, payload.document_id, payload.resource_type
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print(f"DEBUG generation error: {e!r}")
        raise HTTPException(status_code=502, detail="The AI service failed to respond. Please try again.")
    return resource


@router.get("")
def list_resources(document_id: str, user: dict = Depends(get_current_user)):
    _verify_document_ownership(document_id, user["id"])
    resources = resources_collection.find({"document_id": document_id}).sort("created_at", -1)
    return [
        {
            "id": str(r["_id"]),
            "document_id": r["document_id"],
            "resource_type": r["resource_type"],
            "content": r["content"],
            "verification_status": r["verification_status"],
            "created_at": r["created_at"].isoformat(),
        }
        for r in resources
    ]