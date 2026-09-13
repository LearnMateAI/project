"""U-13 — Content-Disposition-safe filenames (`app/routers/documents.py`)."""

from app.routers.documents import _safe_filename


def test_quotes_and_newlines_are_stripped():
    assert '"' not in _safe_filename('report "final".pdf')
    assert "\n" not in _safe_filename("act\nNo.1.pdf")
    assert _safe_filename('report "final".pdf') == "report _final_.pdf"


def test_empty_falls_back():
    assert _safe_filename("") == "document.pdf"
    assert _safe_filename(None) == "document.pdf"
