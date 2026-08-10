from fastapi.responses import Response
from bson import ObjectId
from bson.errors import InvalidId
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Depends, BackgroundTasks

from database.db import documents_collection, fs, chunks_collection
from app_infrastructure.middleware import get_current_user
from document_processing_pipeline.pdf_manager.upload import handle_upload
from document_processing_pipeline.pdf_manager.pdf_manager import process_document

router = APIRouter(prefix="/api/documents", tags=["documents"])

@router.post("/upload", status_code=201)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    subject: str = Form("General"),
    user: dict = Depends(get_current_user),
):
    file_bytes = await file.read()
    try:
        document = handle_upload(
            fs, documents_collection, file_bytes, file.content_type, file.filename, user["id"], subject
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    background_tasks.add_task(
        process_document, file_bytes, documents_collection, chunks_collection, document["id"]
    )
    return document


@router.get("")
def list_documents(user: dict = Depends(get_current_user)):
    docs = documents_collection.find({"owner_id": user["id"]})
    return [
        {
            "id": str(d["_id"]),
            "filename": d["filename"],
            "upload_date": d["upload_date"].isoformat(),
            "subject": d["subject"],
            "page_count": d["page_count"],
            "file_size": d["file_size"],
            "processing_status": d["processing_status"],
            "chunk_count": d.get("chunk_count", 0),
        }
        for d in docs
    ]

@router.get("/{document_id}/file")
def get_document_file(document_id: str, user: dict = Depends(get_current_user)):
    try:
        doc= documents_collection.find_one({"_id": ObjectId(document_id)})
    except InvalidId:
        raise HTTPException(status_code=400, detail="Invalid document id.")

    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")
    if doc["owner_id"] != user["id"]:
        raise HTTPException(status_code=403, detail="You do not have access to this document.")

    grid_out = fs.get(doc["gridfs_file_id"])
    file_bytes = grid_out.read()

    return Response(content=file_bytes, media_type="application/pdf")    