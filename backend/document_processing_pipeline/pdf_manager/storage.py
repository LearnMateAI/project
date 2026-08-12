from datetime import datetime, timezone

def store_pdf(fs, documents_collection, file_bytes: bytes, filename:str, owner_id: str, subject: str, page_count:int) -> dict:
    """
    Saves the raw PDF into GridFS, then creates a metadata record in the
    documents collection referencing it (SRS §3.10 Document entity).
    """
    gridfs_id = fs.put(file_bytes, filename=filename, content_type="application/pdf")

    document = {
        "owner_id": owner_id,
        "filename": filename,
        "upload_date": datetime.now(timezone.utc),
        "subject": subject,
        "page_count": page_count,
        "file_size": len(file_bytes),
        "gridfs_file_id": gridfs_id,
        # SRS FR-5 specifies status "Processing" immediately after upload.
        # Simplified to "Uploaded" here since the real parsing pipeline
        # (FR-6 cleaning / FR-7 parsing) isn't built until Day 7 — the full
        # Processing -> Ready / Failed Validation lifecycle starts then.
        "processing_status": "Uploaded",
    }

    result = documents_collection.insert_one(document)

    return {
        "id": str(result.inserted_id),
        "filename": filename,
        "upload_date": document["upload_date"].isoformat(),
        "subject": subject,
        "page_count": page_count,
        "file_size": document["file_size"],
        "processing_status": document["processing_status"],
    }