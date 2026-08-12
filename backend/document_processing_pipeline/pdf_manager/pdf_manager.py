import os
import tempfile

from bson import ObjectId

from document_processing_pipeline.doc_parser.main import extract_text_from_pdf
from document_processing_pipeline.doc_cleaner.main import clean_pages
from document_processing_pipeline.chunker.chunking import chunk_document
from services.learnmate_bridge import run_ingest


def process_document(file_bytes: bytes, documents_collection, chunks_collection, document_id: str) -> int:
    """
    Retired from the live upload flow as of Day 10 in favour of
    process_document_via_learnmate below, which delegates to components-Dinura's local
    model pipeline instead. Left in place, unused: it's still explainable code from an
    earlier milestone, and nothing requires deleting working code to replace it.
    """
    try:
        pages = extract_text_from_pdf(file_bytes)
        cleaned_pages = clean_pages(pages)
        chunks = chunk_document(cleaned_pages)

        for chunk in chunks:
            chunks_collection.insert_one({
                "document_id": document_id,
                "chunk_index": chunk["chunk_index"],
                "page_number": chunk["page_number"],
                "text": chunk["text"],
            })

        documents_collection.update_one(
            {"_id": ObjectId(document_id)},
            {"$set": {"processing_status": "Ready", "chunk_count": len(chunks)}},
        )
        return len(chunks)

    except Exception as e:
        documents_collection.update_one(
            {"_id": ObjectId(document_id)},
            {"$set": {"processing_status": "Failed Processing", "processing_error": str(e)}},
        )
        raise


def process_document_via_learnmate(file_bytes: bytes, documents_collection, document_id: str) -> dict:
    """
    delegate PDF processing to components-Dinura's local pipeline.

    Writes the uploaded bytes to a temp file (the bridge script takes a path, not bytes),
    runs ingestion in its own process, then folds the result back into this backend's own
    documents_collection record, which stays the source of truth for ownership, subject
    and processing_status. learnmate's own doc_id is stored alongside for Day 11
    (resource generation) and Day 12 (chat) to use.

    document_id doubles as the learnmate session_id -- see learnmate_bridge.py's
    docstring for why that's a safe 1:1 mapping.
    """
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(file_bytes)
            tmp_path = tmp.name

        report = run_ingest(tmp_path, session_id=document_id)

        documents_collection.update_one(
            {"_id": ObjectId(document_id)},
            {"$set": {
                "processing_status": "Ready",
                "page_count": report["n_pages"],
                "chunk_count": report["n_chunks"],
                "learnmate_doc_id": report["doc_id"],
                "learnmate_session_id": document_id,
            }},
        )
        return report

    except Exception as e:
        documents_collection.update_one(
            {"_id": ObjectId(document_id)},
            {"$set": {"processing_status": "Failed Processing", "processing_error": str(e)}},
        )
        raise
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)
