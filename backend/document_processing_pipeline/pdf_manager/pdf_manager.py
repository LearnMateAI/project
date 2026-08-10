from bson import ObjectId

from document_processing_pipeline.doc_parser.main import extract_text_from_pdf
from document_processing_pipeline.doc_cleaner.main import clean_pages
from document_processing_pipeline.chunker.chunking import chunk_document

def process_document(file_bytes: bytes, documents_collection, chunks_collection, document_id: str) -> int:
    """
    Runs the (simplified) processing pipeline for one uploaded PDF:
    extract -> clean -> chunk -> store chunks -> update document status.
    Returns the number of chunks created.
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