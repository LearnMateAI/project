"""
Ingesting one PDF, end to end.

    read + validate  ->  store (GridFS)  ->  extract + clean  ->  split  ->  embed
                                                                              |
                                            bind the session to the document <-

The order is the point of this file. Everything after "store" is the expensive part --
extraction, splitting, and a few thousand embeddings on CPU -- so every rule that could
refuse the upload is checked before any of it starts:

    empty file            pdf_store.read_source
    over MAX_PDF_MB       pdf_store.read_source
    session already used  sessions.check_free

and the session binding is written at the *end*, once the document has proved usable.

The work itself lives in the modules this one calls: clean.py extracts, chunking.py
splits, the vector store embeds. `ingest_pdf` only decides what happens in what order.
"""

import hashlib
import time
from pathlib import Path
from typing import Dict, Iterable, Union

from ..storage import pdf_store
from ..storage.vectors import get_vector_store
from . import sessions
from .chunking import pages_to_documents
from .clean import preprocess


def ingest_pdf(source: Union[str, Path, bytes], filename: str = None,
               session_id: str = None, session_for: Union[str, Iterable[str]] = "chat",
               force: bool = False, verbose: bool = True, user_id: str = None,
               on_progress=None) -> Dict:
    """
    Store and index one PDF, for one session.

    `source` is a path or raw bytes, so this serves a CLI argument and an HTTP upload
    equally. Returns a report with the document record and what was indexed.

    `session_id` binds the document to a session, and `session_for` says what that session
    is for -- "chat", "resource", or "both". A session holds one PDF: a second, different
    PDF ingested into the same session is refused before any work is done.

    A PDF already ingested is skipped unless `force` is set. Identity is the hash of the
    file's bytes, so re-uploading the same document under a new name -- or opening a
    second session on it for the other purpose -- costs nothing rather than re-embedding
    a few thousand chunks.
    """
    def log(message):
        if verbose:
            print(message)
        # Ingestion runs on the job queue in the server, where nobody is watching stdout;
        # this is what puts the same commentary on the job record. Never allowed to raise:
        # a failed progress write must not lose a document that was successfully embedded.
        if on_progress:
            try:
                on_progress(message)
            except Exception:
                pass

    started = time.time()
    kinds = sessions.normalise_kinds(session_for)

    # --- Validate, before anything is written ----------------------------------------
    # read_source raises on an empty file and on one over the size limit; check_free
    # raises when this session already has a different PDF. All of it while the session's
    # existing document is still untouched.
    data, filename = pdf_store.read_source(source, filename)
    digest = hashlib.sha256(data).hexdigest()
    sessions.check_free(session_id, digest, filename)

    document = pdf_store.store_pdf(data, filename=filename)
    doc_id = document["_id"]

    # The status a client polls on. Set before the slow part rather than after, so an
    # upload never sits at "Uploaded" for the several minutes it is actually being read.
    pdf_store.set_status(doc_id, pdf_store.PROCESSING)

    store = get_vector_store()
    already_indexed = store.count(doc_id)

    # --- Already done? Bind and stop --------------------------------------------------
    # This is the path a second session on the same PDF takes -- and why opening a
    # resource session for a PDF already ingested for chat is nearly free.
    if document.get("existing") and already_indexed and not force:
        log(f"[=] Already ingested: {document['filename']} "
            f"({already_indexed} chunks). Use force=True to re-index.")
        # An older record may predate the status field, or have been left mid-flight by a
        # crashed run; either way its chunks are in the store, so it is Ready.
        pdf_store.set_status(doc_id, pdf_store.READY)
        sessions.bind(session_id, doc_id, document["filename"], digest, kinds, log,
                      user_id)
        return _report(document, doc_id, session_id, kinds, skipped=True,
                       n_pages=document.get("n_pages"), n_chunks=already_indexed,
                       started=started)

    log(f"[*] Stored {document['filename']} "
        f"({document['size_bytes'] / 1_048_576:.1f} MB) as {doc_id}")

    # Everything from here on can fail on the document's own content -- a scan with no
    # text layer, a PDF of nothing but contents pages -- and the record already exists by
    # now. Without this the document would sit at "Processing" forever and the user would
    # have no way to tell a slow ingest from a dead one.
    try:
        # --- Extract ------------------------------------------------------------------
        # `data` is what store_pdf just wrote or, on the dedupe path, is byte-identical to
        # it -- a document is keyed on the SHA-256 of exactly these bytes. Reading them
        # back out of GridFS here would be a second transfer of a file already in hand,
        # which on the upload path is the third time those bytes have moved.
        pages = preprocess(data)
        if not pages:
            raise ValueError(
                f"No extractable text in {document['filename']}. If it is a scanned PDF "
                "it needs OCR before it can be indexed."
            )
        log(f"[*] Extracted {len(pages)} pages with text")

        # --- Split --------------------------------------------------------------------
        documents = pages_to_documents(pages, doc_id, document["filename"])
        if not documents:
            raise ValueError(
                f"No substantive chunks produced from {document['filename']}.")
        log(f"[*] {len(pages)} pages -> {len(documents)} chunks")

        if force and already_indexed:
            # Clear both collections before rewriting. Upserting alone would leave behind
            # any page or chunk the new run no longer produces -- which is exactly what
            # happens when a filter is tightened and pages start being dropped.
            store.delete(doc_id=doc_id)
            pdf_store.delete_pages(doc_id)
            from ..storage import bm25_store
            bm25_store.delete_for(doc_id)

        # --- Store the readable text --------------------------------------------------
        # Chunks are shaped for retrieval; resource generation wants the page as it reads.
        # This is what makes a "resource" session possible at all -- see source_text.py.
        indexed_pages = {doc.metadata["page_number"] for doc in documents}
        pdf_store.store_pages(
            doc_id, [p for p in pages if p["page_number"] in indexed_pages])

        # --- Embed --------------------------------------------------------------------
        log(f"[*] Embedding {len(documents)} chunks into {store.describe_backend()}...")
        store.add_documents(documents)
        from ..storage import bm25_store
        bm25_store.index_documents(doc_id, documents)
        # Also flips the status to Ready.
        pdf_store.mark_ingested(doc_id, len(pages), len(documents))
    except Exception as exc:
        pdf_store.set_status(doc_id, pdf_store.FAILED, str(exc))
        raise

    # --- Bind -------------------------------------------------------------------------
    # Only now that the document is genuinely usable. Binding earlier would tie the
    # session to a PDF that turned out to have no extractable text, and the user could
    # not then ingest a working one without abandoning the session.
    sessions.bind(session_id, doc_id, document["filename"], digest, kinds, log, user_id)

    log(f"[+] Ingested {document['filename']} in {round(time.time() - started, 2)}s")
    return _report(pdf_store.get_document(doc_id), doc_id, session_id, kinds,
                   skipped=False, n_pages=len(pages), n_chunks=len(documents),
                   started=started)


def _report(document, doc_id, session_id, kinds, skipped, n_pages, n_chunks,
            started) -> Dict:
    """The shape every caller gets back, from both exits above."""
    return {
        "document": document,
        "doc_id": str(doc_id),
        "session_id": session_id,
        "session_for": list(kinds),
        "skipped": skipped,
        "n_pages": n_pages,
        "n_chunks": n_chunks,
        "elapsed_s": round(time.time() - started, 2),
    }
