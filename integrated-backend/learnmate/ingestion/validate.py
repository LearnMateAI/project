"""
Refusing an upload before any work is spent on it.

Ingestion is expensive -- extraction, splitting, and a few thousand embeddings through a
CPU model -- so everything that can reject a file is checked first, and every message here
is written to be shown to the person who uploaded it rather than logged.

    is it a PDF at all       extension and content type
    is it small enough       MAX_PDF_MB, checked again in pdf_files.read_source
    can it be opened         corrupt files and password-protected ones fail the same way
    how many pages           1..MAX_PAGE_COUNT

Size and page count are two different limits on purpose: a 3 MB scan of 800 pages is a
small file and a very long ingest.

The page count is returned rather than discarded -- the upload handler stores it on the
document record, so the number the user is shown comes from the same read that validated
the file.
"""

from typing import Optional

from .. import config

ALLOWED_CONTENT_TYPES = ("application/pdf", "application/x-pdf", "application/octet-stream")


def validate_pdf(file_bytes: bytes, filename: str,
                 content_type: Optional[str] = None) -> int:
    """
    Check an upload is a PDF this system will accept. Returns its page count.

    Raises ValueError with a human-readable message on any failure; the API layer turns
    that into a 400 with the message passed through unchanged.
    """
    import fitz  # PyMuPDF, the same reader ingestion itself uses

    if not (filename or "").lower().endswith(".pdf"):
        raise ValueError("Only PDF files are allowed.")

    # Browsers send application/pdf; some send octet-stream for a file dragged from disk,
    # which is why that is allowed and the extension check above is the real gate.
    if content_type and content_type.split(";")[0].strip() not in ALLOWED_CONTENT_TYPES:
        raise ValueError(f"Unsupported file type {content_type!r}. Please upload a PDF.")

    if not file_bytes:
        raise ValueError("This file is empty.")

    if len(file_bytes) > config.MAX_PDF_BYTES:
        raise ValueError(
            f"{filename} is {len(file_bytes) / 1_048_576:.1f} MB, over the "
            f"{config.MAX_PDF_MB:g} MB upload limit."
        )

    try:
        document = fitz.open(stream=file_bytes, filetype="pdf")
    except Exception:
        raise ValueError(
            "This PDF could not be read. It may be corrupted -- please try uploading it "
            "again, or export a fresh copy."
        )

    try:
        # Encryption is reported rather than lumped in with corruption, because the two
        # have completely different fixes and the user knows which one applies.
        if document.needs_pass:
            raise ValueError(
                "This PDF is password-protected. Please upload an unprotected copy."
            )
        page_count = document.page_count
    finally:
        document.close()

    if page_count == 0:
        raise ValueError("This PDF appears to have no pages.")
    if page_count > config.MAX_PAGE_COUNT:
        raise ValueError(
            f"{filename} has {page_count} pages, over the {config.MAX_PAGE_COUNT}-page "
            f"limit."
        )

    return page_count
