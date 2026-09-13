"""U-11 — page cleaning, TOC skip, chunk provenance (`clean.py`, `chunking.py`)."""

from learnmate.ingestion.clean import clean_text, is_substantive, looks_like_contents
from learnmate.ingestion.chunking import pages_to_documents


def test_clean_text_flattens_typography_and_hyphenation():
    raw = "The “Cabinet” shall\noff-\nshore the fund.\n12\n"
    cleaned = clean_text(raw)
    assert '"Cabinet"' in cleaned or "Cabinet" in cleaned
    assert "offshore" in cleaned
    assert "\n" not in cleaned


def test_looks_like_contents_detects_dot_leaders():
    toc = "Chapter I .......... 1\nChapter II .......... 5\nChapter III .......... 9\n"
    assert looks_like_contents(toc, min_leaders=3) is True
    assert looks_like_contents("Section 108. The court may...") is False


def test_is_substantive_ignores_punctuation():
    assert is_substantive(".........", min_chars=8) is False
    assert is_substantive("Directors owe fiduciary duties.", min_chars=8) is True


def test_contents_pages_are_not_chunked():
    toc = "Intro .......... 1\nPart A .......... 4\nPart B .......... 9\nIndex .......... 40\n"
    docs = pages_to_documents(
        [{"page_number": 1, "page_content": toc}],
        doc_id="d1",
        filename="act.pdf",
    )
    assert docs == []


def test_prose_chunks_carry_page_and_index():
    page = (
        "Section 108. The officer in charge shall keep a record of every statement. "
        "The record shall be produced to the court when so required. "
        "Failure to keep the record is an offence under this Part."
    )
    docs = pages_to_documents(
        [{"page_number": 12, "page_content": page}],
        doc_id="d1",
        filename="cpc.pdf",
    )
    assert len(docs) >= 1
    assert docs[0].metadata["page_number"] == 12
    assert docs[0].metadata["doc_id"] == "d1"
    assert docs[0].metadata["chunk_index"] == 0
    assert docs[0].metadata["filename"] == "cpc.pdf"
