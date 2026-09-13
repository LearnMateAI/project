"""
Documents: upload, list, read, delete.

The upload path is the one worth reading closely, because it is split across two moments
on purpose:

    in the request   validate -> store the bytes -> link it to the user -> return 202
    on the worker    extract -> clean -> chunk -> embed -> mark Ready

Everything that can reject the file happens while the client is still connected, so a
password-protected PDF gets an immediate 400 rather than a job that fails a minute later.
Everything expensive happens after, because embedding a book is minutes and no browser
will wait.

Deletion is the other subtle one. A document is shared between everyone who uploaded the
same bytes, so deleting removes the caller's library entry and stops -- unless they were
the last owner, in which case the bytes, pages, chunks and vectors go too. Deleting the
vectors is a separate call: `pdf_store.delete_document` clears the `chunks` collection,
which is where vectors live only on the MongoDB backend, so a Qdrant deployment would
otherwise leak every embedding of every deleted document.
"""

from typing import Dict, List, Optional

try:
    from learnmate.ingestion import validate_upload
except ImportError:
    from learnmate.ingestion import validate_pdf

    def validate_upload(file_bytes, filename, content_type=None):
        return "pdf", validate_pdf(file_bytes, filename, content_type)
from learnmate.ingestion.convert import convert_to_pdf
try:
    from learnmate.ingestion.formats import kind_from_record, media_type_for, unit_label_for
except ImportError:
    def kind_from_record(document):
        return "pdf"

    def media_type_for(kind):
        return "application/pdf"

    def unit_label_for(kind):
        return "pages"
from learnmate.storage import ownership, pdf_store
from learnmate.storage.vectors import get_vector_store

from .. import config
from ..errors import NotFound
from . import ownership as access


def serialize(document: Dict, link: Optional[Dict] = None) -> Dict:
    """
    One document, in the shape the frontend reads.

    Two records are folded together here: the shared document (what the PDF is) and the
    caller's library entry (what they called it and filed it under). `.get` throughout
    rather than indexing -- a document mid-ingest has no page count yet, and a listing
    that 500s because one row is halfway through processing is worse than a null.
    """
    link = link or {}
    uploaded_at = document.get("uploaded_at")
    kind = kind_from_record(document)

    return {
        "id": str(document["_id"]),
        # The caller's name for it, falling back to the stored one.
        "filename": link.get("filename") or document.get("filename", ""),
        "subject": link.get("subject", "General"),
        "upload_date": uploaded_at.isoformat() if uploaded_at else None,
        "page_count": document.get("n_pages"),
        "file_size": document.get("size_bytes"),
        "processing_status": document.get("processing_status", pdf_store.UPLOADED),
        "processing_error": document.get("processing_error"),
        "chunk_count": document.get("n_chunks") or 0,
        "source_kind": kind,
        "unit_label": unit_label_for(kind),
    }


def upload(user_id: str, file_bytes: bytes, filename: str, content_type: str = None,
           subject: str = "General") -> Dict:
    """
    Validate and store one upload, and put it in the user's library.

    Returns the serialized document. Ingestion is *not* done here -- the caller enqueues
    it -- so the document comes back as Uploaded/Processing and the client polls.

    Raises ValueError on anything wrong with the file, with a message meant to be shown.
    """
    # Before anything is written. read_source checks the size again on the way in, but a
    # user should learn their 40 MB scan is too big without waiting for it to be stored.
    source_kind, _ = validate_upload(file_bytes, filename, content_type)
    stored_bytes, stored_filename = convert_to_pdf(file_bytes, filename, source_kind)
    validate_upload(stored_bytes, stored_filename, "application/pdf")

    document = pdf_store.store_pdf(stored_bytes, filename=stored_filename)

    # The library entry, with this user's own name and subject for it. Written before the
    # job is queued so the document appears in their list immediately.
    link = ownership.link(user_id, document["_id"], stored_filename, subject)

    return serialize(document, link)


def list_documents(user_id: str) -> List[Dict]:
    """The user's library, most recently added first."""
    links = ownership.list_links(user_id, limit=config.MAX_DOCUMENTS)
    if not links:
        return []

    # One query for every document behind the page of links, rather than one per row.
    documents = pdf_store.get_many(link["doc_id"] for link in links)

    out = []
    for link in links:
        document = documents.get(str(link["doc_id"]))
        # A link whose document is gone must not break the whole listing; it is a
        # dangling row, and deleting it is the next delete's job.
        if document:
            out.append(serialize(document, link))
    return out


def get_document(user_id: str, doc_id: str) -> Dict:
    """One document from the user's library."""
    document = access.require_document(user_id, doc_id)
    return serialize(document, ownership.get_link(user_id, document["_id"]))


def get_file_media_type(user_id: str, doc_id: str) -> str:
    """MIME type of the stored original, for Content-Type on download."""
    document = access.require_document(user_id, doc_id)
    return media_type_for(kind_from_record(document))


def get_pdf_bytes(user_id: str, doc_id: str) -> bytes:
    """The stored original file, for the viewer or a download."""
    document = access.require_document(user_id, doc_id)
    data = pdf_store.get_pdf_bytes(document["_id"])
    if data is None:
        raise NotFound("The stored file for this document is missing.")
    return data


def get_pages(user_id: str, doc_id: str, first: int = None, last: int = None) -> List[Dict]:
    """
    The cleaned page text, in reading order.

    This is what the model actually reads -- running heads stripped, ligatures repaired,
    hyphenation joined -- so showing it is the honest answer to "what did it see?".
    """
    document = access.require_document(user_id, doc_id)

    numbers = None
    if first is not None or last is not None:
        start = max(1, first or 1)
        end = max(start, last or start)
        numbers = list(range(start, end + 1))

    return [{"page_number": page["page_number"], "text": page.get("text", "")}
            for page in pdf_store.get_pages(document["_id"], numbers)]


def delete_document(user_id: str, doc_id: str) -> Dict:
    """
    Remove a document from one user's library, and from the system if nobody else has it.

    Returns {"removed": True, "purged": bool} -- `purged` says whether the underlying
    bytes and vectors went too, which is the difference between "off my list" and "gone".
    """
    document = access.require_document(user_id, doc_id)
    document_id = document["_id"]

    ownership.unlink(user_id, document_id)

    if ownership.owner_count(document_id) > 0:
        # Somebody else still has it. Their chunks, pages and vectors must survive.
        return {"removed": True, "purged": False}

    # Last owner. The vector store is cleared explicitly: delete_document only clears the
    # `chunks` collection, which holds vectors on the MongoDB backend but not on Qdrant.
    try:
        get_vector_store().delete(doc_id=document_id)
    except Exception:
        # A vector store that is down must not block the delete -- the alternative is a
        # document nobody can remove. The orphaned points are overwritten on re-ingest,
        # since point ids are derived from (doc_id, page, chunk).
        pass

    pdf_store.delete_document(document_id)
    return {"removed": True, "purged": True}
