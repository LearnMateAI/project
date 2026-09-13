"""
Refusing an upload before any work is spent on it.

Ingestion is expensive -- extraction, splitting, and a few thousand embeddings through a
CPU model -- so everything that can reject the file is checked first, and every message
here is written to be shown to the person who uploaded it rather than logged.

    is it a supported kind   pdf / docx / pptx / tex
    is it small enough       MAX_PDF_MB (the upload ceiling, not PDF-specific)
    can it be opened         corrupt, encrypted, or empty-of-text files fail here
    how many units           PDF pages, slides, Word slices, or TeX sections

The unit count is returned rather than discarded -- the upload handler stores it on the
document record, so the number the user is shown comes from the same read that validated
the file.
"""

from typing import Optional, Tuple

from .. import config
from .formats import (
    ALLOWED_CONTENT_TYPES,
    KIND_DOCX,
    KIND_PDF,
    KIND_PPTX,
    KIND_TEX,
    confirm_kind,
    detect_kind,
)


def validate_upload(file_bytes: bytes, filename: str,
                    content_type: Optional[str] = None) -> Tuple[str, int]:
    """
    Check an upload is a source this system will accept.

    Returns (kind, unit_count). Raises ValueError with a human-readable message.
    """
    kind = detect_kind(filename)

    if content_type and content_type.split(";")[0].strip() not in ALLOWED_CONTENT_TYPES:
        raise ValueError(
            f"Unsupported file type {content_type!r}. "
            "Upload a PDF, Word (.docx), PowerPoint (.pptx), or LaTeX (.tex) file."
        )

    if not file_bytes:
        raise ValueError("This file is empty.")

    if len(file_bytes) > config.MAX_PDF_BYTES:
        raise ValueError(
            f"{filename} is {len(file_bytes) / 1_048_576:.1f} MB, over the "
            f"{config.MAX_PDF_MB:g} MB upload limit."
        )

    confirm_kind(kind, file_bytes)

    if kind == KIND_PDF:
        return kind, _pdf_page_count(file_bytes, filename)
    if kind == KIND_DOCX:
        return kind, _count_office(file_bytes, kind)
    if kind == KIND_PPTX:
        return kind, _count_office(file_bytes, kind)
    return kind, _tex_section_count(file_bytes)


def validate_pdf(file_bytes: bytes, filename: str,
                 content_type: Optional[str] = None) -> int:
    """PDF-only wrapper kept for callers that still expect a page count."""
    kind, count = validate_upload(file_bytes, filename, content_type)
    if kind != KIND_PDF:
        raise ValueError("Only PDF files are allowed.")
    return count


def _pdf_page_count(file_bytes: bytes, filename: str) -> int:
    import fitz  # PyMuPDF, the same reader ingestion itself uses

    try:
        document = fitz.open(stream=file_bytes, filetype="pdf")
    except Exception:
        raise ValueError(
            "This PDF could not be read. It may be corrupted -- please try uploading it "
            "again, or export a fresh copy."
        )

    try:
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


def _count_office(file_bytes: bytes, kind: str) -> int:
    from .extract_office import extract_docx, extract_pptx

    pages = extract_docx(file_bytes) if kind == KIND_DOCX else extract_pptx(file_bytes)
    if not pages:
        label = "Word document" if kind == KIND_DOCX else "PowerPoint deck"
        raise ValueError(
            f"No extractable text in this {label}. "
            "Image-only slides or an empty file cannot be indexed."
        )
    if len(pages) > config.MAX_PAGE_COUNT:
        raise ValueError(
            f"This file has {len(pages)} extractable units, over the "
            f"{config.MAX_PAGE_COUNT}-page limit."
        )
    return len(pages)


def _tex_section_count(file_bytes: bytes) -> int:
    from .extract_office import extract_tex

    pages = extract_tex(file_bytes)
    if not pages:
        raise ValueError(
            "No extractable text in this LaTeX file. "
            "A preamble-only or command-only source cannot be indexed."
        )
    if len(pages) > config.MAX_PAGE_COUNT:
        raise ValueError(
            f"This LaTeX file has {len(pages)} sections, over the "
            f"{config.MAX_PAGE_COUNT}-page limit."
        )
    return len(pages)
