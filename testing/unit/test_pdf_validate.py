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
    with pytest.raises(ValueError, match="Only PDF"):
        validate_pdf(b"%PDF", "notes.txt", "application/pdf")


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
    with pytest.raises(ValueError, match="could not be read"):
        validate_pdf(b"not-a-pdf-at-all", "notes.pdf", "application/pdf")
