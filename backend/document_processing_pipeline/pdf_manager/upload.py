from document_processing_pipeline.pdf_manager.validation import validate_pdf
from document_processing_pipeline.pdf_manager.storage import store_pdf

def handle_upload(fs, documents_collection, file_bytes: bytes, content_type: str, filename: str, owner_id: str, subject: str) -> dict:
    """
    Orchestrates one uploaded file: validate first, then store.
    Raises ValueError (caught in api/documents.py) on any validation failure.
    """
    page_count = validate_pdf(file_bytes, content_type, filename)
    return store_pdf(fs, documents_collection, file_bytes, filename, owner_id, subject, page_count)