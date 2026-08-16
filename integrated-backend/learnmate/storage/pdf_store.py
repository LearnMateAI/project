"""
PDF storage: the facade over the three modules that make it up.

    pdf_files.py  the bytes, in GridFS
    documents.py  the record describing them, and every way of finding it
    pages.py      the cleaned page text derived from them

Kept as one importable name because that is how the rest of the system already reads --
`pdf_store.store_pdf(...)`, `pdf_store.get_pages(...)` -- and because the three genuinely
are one subject seen from three angles. Import the specific module when you want to know
which layer you are touching; import this when you just want to store or fetch a PDF.
"""

from .documents import (
    FAILED,
    PROCESSING,
    READY,
    UPLOADED,
    delete_document,
    export_pdf,
    find_by_hash,
    get_active_document,
    get_document,
    get_many,
    get_pdf_bytes,
    list_documents,
    mark_ingested,
    resolve_document,
    set_status,
    stale_embeddings,
    store_pdf,
)
from .pages import count_pages, delete_pages, get_pages, store_pages
from .pdf_files import read_source

__all__ = [
    "FAILED",
    "PROCESSING",
    "READY",
    "UPLOADED",
    "count_pages",
    "delete_document",
    "delete_pages",
    "export_pdf",
    "find_by_hash",
    "get_active_document",
    "get_document",
    "get_many",
    "get_pages",
    "get_pdf_bytes",
    "list_documents",
    "mark_ingested",
    "read_source",
    "resolve_document",
    "set_status",
    "stale_embeddings",
    "store_pages",
    "store_pdf",
]
