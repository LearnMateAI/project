"""
PDF ingestion: extract, clean, split, embed, store -- for one session.

    read + validate  ->  store (GridFS)  ->  extract + clean  ->  split  ->  embed
                                                                              |
                                            bind the session to the document <-

An upload always belongs to a session, and a session is opened for one purpose:

    chat      the PDF will be asked questions about, through the chat agent
    resource  MCQs, summaries and key points will be generated from it
    both      one PDF serving the whole workflow

Both purposes need identical ingestion -- the same chunks for retrieval and the same
stored page text -- so the kind is a statement of intent, not an optimisation. It is
checked when a command runs, so `generate` against a session opened for chat says so
plainly instead of quietly doing something the user did not set up. Opening a second
session on an already-ingested PDF is nearly free: nothing is re-embedded.

Where things live, in reading order:

    validate.py    refusing an upload before any work is spent on it
    clean.py       page extraction and cleaning (running heads, ligatures, hyphenation)
    chunking.py    cleaned pages -> the overlapping chunks that get embedded
    sessions.py    session kinds, one-PDF-per-session, and the binding
    pipeline.py    ingest_pdf() -- the order all of the above happens in
    source_text.py build_source_text() -- what a resource session reads back out

The split between chunking.py and source_text.py is the one worth understanding: chunks
are sized and overlapped for *retrieval*, whole pages are kept for *reading*, and the two
are not interchangeable. Joining chunks back together repeats text at every boundary and
starts mid-sentence.
"""

from .chunking import build_splitter, pages_to_documents
from .clean import clean_text, extract_pages, is_substantive, preprocess
from .pipeline import ingest_pdf
from .sessions import (
    SESSION_KINDS,
    describe_kinds,
    kinds_for,
    normalise_kinds,
    require_kind,
)
from .source_text import build_source_text
from .formats import detect_kind, kind_from_record
from .validate import validate_pdf, validate_upload

__all__ = [
    "SESSION_KINDS",
    "build_source_text",
    "build_splitter",
    "clean_text",
    "describe_kinds",
    "extract_pages",
    "ingest_pdf",
    "is_substantive",
    "kinds_for",
    "normalise_kinds",
    "pages_to_documents",
    "preprocess",
    "require_kind",
    "detect_kind",
    "kind_from_record",
    "validate_pdf",
    "validate_upload",
]
