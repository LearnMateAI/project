"""
Documents: upload, list, read, delete.

Upload is the endpoint whose shape changed from the original backend, and the reason is
worth stating. It returns **202 with a job id**, not 201 with a finished document: reading
a PDF means extracting it, cleaning it, splitting it and pushing a few thousand chunks
through an embedding model, which is minutes on CPU. The document row and the caller's
library entry are written before the response, so it appears in their list immediately as
`Processing`; the client polls `GET /api/jobs/{job_id}` until the status is `Ready`.

Everything that can reject the file -- not a PDF, too big, too many pages, encrypted,
corrupt -- happens inside the request, so a bad upload is an immediate 400 rather than a
job that fails a minute later.
"""

import re

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from fastapi.responses import Response

from ..deps import get_current_user
from ..jobs import enqueue
from ..services import documents as service

router = APIRouter(prefix="/api/documents", tags=["documents"])

# Filenames come from an upload, so they are whatever the uploader's filesystem allowed --
# including a quote or a newline, which would end the Content-Disposition value early and
# let the rest be read as another header. Only these characters go into the header; the
# real filename is untouched everywhere else.
_HEADER_SAFE = re.compile(r"[^A-Za-z0-9 ._()\[\]-]")


def _safe_filename(filename: str) -> str:
    """A filename reduced to what is safe to put in a response header."""
    return _HEADER_SAFE.sub("_", filename or "document.pdf")[:120] or "document.pdf"


@router.post("", status_code=202)
@router.post("/upload", status_code=202)
async def upload_document(
    file: UploadFile = File(...),
    subject: str = Form("General"),
    user: dict = Depends(get_current_user),
):
    """
    Store a PDF, Word, PowerPoint or LaTeX file and queue it for processing.

    Returns {document, job_id}. The document is usable for nothing until its
    `processing_status` reaches "Ready".
    """
    file_bytes = await file.read()

    # Raises ValueError -> 400 with a message meant to be read by whoever uploaded it.
    document = service.upload(
        user["id"], file_bytes, file.filename or "upload.pdf", file.content_type, subject)

    job = enqueue(
        user["id"], "ingest",
        {"document_id": document["id"], "filename": document["filename"]},
        message="Waiting to be processed.",
    )

    return {"document": document, "job_id": str(job["_id"]), "status": job["status"]}


@router.get("")
def list_documents(user: dict = Depends(get_current_user)):
    """Everything in this user's library, most recently added first."""
    return service.list_documents(user["id"])


@router.get("/{document_id}")
def get_document(document_id: str, user: dict = Depends(get_current_user)):
    """One document's metadata, including where it is in processing."""
    return service.get_document(user["id"], document_id)


@router.get("/{document_id}/file")
def get_document_file(document_id: str, user: dict = Depends(get_current_user)):
    """The stored original file, for the viewer or a download."""
    document = service.get_document(user["id"], document_id)
    data = service.get_pdf_bytes(user["id"], document_id)

    return Response(
        content=data,
        media_type=service.get_file_media_type(user["id"], document_id),
        # inline so a browser renders it rather than downloading it; the filename is still
        # what a "save as" will suggest.
        headers={"Content-Disposition":
                 f'inline; filename="{_safe_filename(document["filename"])}"'},
    )


@router.get("/{document_id}/pages")
def get_document_pages(
    document_id: str,
    first: int = Query(None, ge=1, description="first page number, 1-based"),
    last: int = Query(None, ge=1, description="last page number, inclusive"),
    user: dict = Depends(get_current_user),
):
    """
    The cleaned page text.

    Not the raw PDF text: running heads are gone, ligatures repaired, hyphenation joined.
    This is what the models actually read, which makes it the honest answer to "what did
    it see on page 41?".
    """
    return service.get_pages(user["id"], document_id, first, last)


@router.delete("/{document_id}")
def delete_document(document_id: str, user: dict = Depends(get_current_user)):
    """
    Remove a document from this user's library.

    The PDF, its page text and its vectors are deleted only if nobody else has the same
    document -- one file uploaded by several people is stored once, and one person
    deleting it must not break it for the others. `purged` in the response says which
    happened.
    """
    return service.delete_document(user["id"], document_id)
