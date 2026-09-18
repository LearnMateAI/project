"""U-10 — reject a bad upload before embedding (`learnmate/ingestion/validate.py`)."""

import fitz
import pytest

from learnmate.ingestion.validate import validate_pdf


def _pdf_with_text(text: str = "Section 1. Directors owe duties to the company.") -> bytes:
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), text)
    data = document.tobytes()
    document.close()
    return data


def test_non_pdf_extension_rejected():
    # .txt is not a supported kind at all (pdf/docx/pptx/tex); detect_kind rejects it
    # before validate_pdf's own "PDF only" wrapper check ever runs.
    with pytest.raises(ValueError, match="Upload a PDF"):
        validate_pdf(b"%PDF", "notes.txt", "application/pdf")


def _docx_bytes(text: str = "Directors owe fiduciary duties to the company.") -> bytes:
    from io import BytesIO

    from docx import Document

    document = Document()
    document.add_paragraph(text)
    buffer = BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def test_recognised_non_pdf_kind_rejected_by_pdf_only_wrapper():
    # A kind the multi-format pipeline supports (docx) still isn't a PDF, so the
    # PDF-only wrapper used by legacy callers must refuse it explicitly.
    with pytest.raises(ValueError, match="Only PDF files are allowed"):
        validate_pdf(_docx_bytes(), "notes.docx", "application/pdf")


def test_empty_file_rejected():
    with pytest.raises(ValueError, match="empty"):
        validate_pdf(b"", "notes.pdf", "application/pdf")


def test_unsupported_content_type_rejected():
    with pytest.raises(ValueError, match="Unsupported file type"):
        validate_pdf(_pdf_with_text(), "notes.pdf", "image/png")


def test_octet_stream_allowed_when_extension_is_pdf():
    pages = validate_pdf(_pdf_with_text(), "notes.pdf", "application/octet-stream")
    assert pages >= 1


def test_valid_pdf_returns_page_count():
    assert validate_pdf(_pdf_with_text(), "act.pdf", "application/pdf") == 1


def test_garbage_bytes_are_corrupt():
    # No %PDF magic bytes at all: rejected by the cheap magic-byte check before
    # PyMuPDF ever opens it.
    with pytest.raises(ValueError, match="not a readable PDF"):
        validate_pdf(b"not-a-pdf-at-all", "notes.pdf", "application/pdf")


def test_pdf_header_with_corrupt_body_is_rejected():
    # Passes the magic-byte check (starts with %PDF) but PyMuPDF still can't parse it,
    # so the deeper "could not be read" branch in _pdf_page_count must still fire.
    with pytest.raises(ValueError, match="could not be read"):
        validate_pdf(b"%PDF-1.4\nthis is not a real pdf body", "notes.pdf", "application/pdf")
