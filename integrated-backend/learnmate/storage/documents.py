"""
The document record: one row per ingested PDF.

    {_id, filename, sha256, size_bytes, gridfs_id, uploaded_at, n_pages, n_chunks,
     ingested_at, processing_status, processing_error}

Identity is the SHA-256 of the file bytes, not the filename. Uploading the same PDF twice
under different names is recognised as one document, which keeps the embedding work from
being repeated and gives every stored resource a stable document to point at.

That is also why there is no owner here: one row can serve several people. Who may see a
document lives in ownership.py, and every access check in the API asks that collection.

`processing_status` is the lifecycle a client watches, because ingestion runs on the job
queue rather than inside the upload request:

    Uploaded -> Processing -+-> Ready
                            |
                            +-> Failed Processing   (with processing_error)

Retrieval is by indexed _id or sha256, so fetching metadata is a single indexed lookup
and fetching bytes is a GridFS read by id.
"""

from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Union

import hashlib

from bson import ObjectId

from .. import config
from . import pdf_files
from .ids import coerce_id
from .mongo import get_db


def _collection():
    return get_db()[config.COLL_DOCUMENTS]


# The processing lifecycle a client polls on. "Ready" is the only status from which a
# document can be chatted with or generated from.
UPLOADED = "Uploaded"
PROCESSING = "Processing"
READY = "Ready"
FAILED = "Failed Processing"


# --- Writing ---------------------------------------------------------------------------

def store_pdf(source: Union[str, Path, bytes], filename: str = None) -> Dict:
    """
    Store a PDF and return its document record.

    `source` is a path or the raw bytes, so this serves both a CLI path argument and an
    HTTP upload without the caller staging a temp file.

    A PDF already present is returned untouched with `existing` set, letting the ingestion
    pipeline skip re-embedding work that has already been done. That is also what makes
    opening a second session on the same PDF nearly free.
    """
    data, filename = pdf_files.read_source(source, filename)
    digest = hashlib.sha256(data).hexdigest()

    existing = _collection().find_one({"sha256": digest})
    if existing:
        existing["existing"] = True
        return existing

    # Bytes first: a record pointing at nothing would be worse than orphaned bytes, which
    # the unique sha256 index means can only ever happen once per file anyway.
    from learnmate.ingestion.formats import detect_kind, media_type_for

    try:
        source_kind = detect_kind(filename)
    except ValueError:
        source_kind = "pdf"

    gridfs_id = pdf_files.put(
        filename, data, digest, content_type=media_type_for(source_kind))

    record = {
        "filename": filename,
        "sha256": digest,
        "size_bytes": len(data),
        "source_kind": source_kind,
        "gridfs_id": gridfs_id,
        "uploaded_at": datetime.now(timezone.utc),
        # Filled in by the ingestion pipeline once the text has been processed.
        "n_pages": None,
        "n_chunks": None,
        "ingested_at": None,
        "processing_status": UPLOADED,
        "processing_error": None,
    }
    record["_id"] = _collection().insert_one(record).inserted_id
    record["existing"] = False
    return record


def mark_ingested(doc_id: Union[str, ObjectId], n_pages: int, n_chunks: int) -> None:
    """Record the outcome of ingestion on the document record."""
    _collection().update_one(
        {"_id": coerce_id(doc_id)},
        {"$set": {"n_pages": n_pages, "n_chunks": n_chunks,
                  "ingested_at": datetime.now(timezone.utc),
                  # Which model produced this document's vectors. Stamped because vectors
                  # from two different embedding models are not comparable and nothing
                  # about them says so: a query embedded by model B against passages
                  # embedded by model A returns confident, meaningless scores. This is what
                  # `stale_embeddings` reads to catch a changed setting before it silently
                  # degrades every answer.
                  "embedding_model": config.EMBEDDING_MODEL,
                  "chunk_size": config.CHUNK_SIZE,
                  "processing_status": READY, "processing_error": None}},
    )


def stale_embeddings() -> List[Dict]:
    """
    Ready documents whose vectors were built by a different embedding model than the one
    now configured.

    Returns the offending records, newest first, so a caller can name them. An empty list
    means everything indexed agrees with the current setting -- including a corpus ingested
    before this field existed, which is left alone rather than assumed stale.
    """
    return list(_collection().find(
        {"processing_status": READY,
         "embedding_model": {"$exists": True, "$ne": config.EMBEDDING_MODEL}},
        {"filename": 1, "embedding_model": 1},
    ).sort("ingested_at", -1))


def set_status(doc_id: Union[str, ObjectId], status: str, error: str = None) -> None:
    """
    Move a document along the processing lifecycle.

    Separate from mark_ingested because the two failure-free transitions happen at
    different moments: this one when the job picks the document up, that one when the
    chunks are actually in the vector store.
    """
    _collection().update_one(
        {"_id": coerce_id(doc_id)},
        {"$set": {"processing_status": status,
                  "processing_error": str(error)[:1000] if error else None}},
    )


def delete_document(doc_id: Union[str, ObjectId]) -> bool:
    """
    Remove a document, its stored PDF and the text derived from it.

    Note this clears the `chunks` collection directly, which is where vectors live only
    on the MongoDB backend. A caller using Qdrant must also delete through the vector
    store -- see ingestion, which does exactly that.
    """
    document = get_document(doc_id)
    if not document:
        return False

    database = get_db()
    database[config.COLL_CHUNKS].delete_many({"doc_id": document["_id"]})
    database[config.COLL_PAGES].delete_many({"doc_id": document["_id"]})
    database[config.COLL_BM25].delete_many({"doc_id": document["_id"]})
    pdf_files.drop(document.get("gridfs_id"))
    database[config.COLL_DOCUMENTS].delete_one({"_id": document["_id"]})
    return True


# --- Reading ---------------------------------------------------------------------------

def get_document(doc_id: Union[str, ObjectId]) -> Optional[Dict]:
    """Look up one document's metadata by id."""
    oid = coerce_id(doc_id)
    if oid is None:
        return None
    return _collection().find_one({"_id": oid})


def find_by_hash(digest: str) -> Optional[Dict]:
    """Look up a document by the SHA-256 of its bytes."""
    return _collection().find_one({"sha256": digest})


def get_pdf_bytes(doc_id: Union[str, ObjectId]) -> Optional[bytes]:
    """Read a stored PDF back out of GridFS."""
    document = get_document(doc_id)
    if not document:
        return None
    return pdf_files.get(document.get("gridfs_id"))


def export_pdf(doc_id: Union[str, ObjectId], destination: Union[str, Path]) -> Path:
    """Write a stored PDF back to disk."""
    data = get_pdf_bytes(doc_id)
    if data is None:
        raise KeyError(f"No stored PDF for document {doc_id}")

    destination = Path(destination)
    if destination.is_dir():
        destination = destination / get_document(doc_id)["filename"]
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(data)
    return destination


def list_documents(limit: int = 50) -> List[Dict]:
    """Most recently uploaded documents first."""
    return list(_collection().find().sort("uploaded_at", -1).limit(limit))


def get_many(doc_ids) -> Dict[str, Dict]:
    """
    Several documents at once, keyed by their id as a string.

    What a library listing needs: the caller has a page of ownership links and wants the
    document behind each, in one query rather than one query per row.
    """
    oids = [oid for oid in (coerce_id(doc_id) for doc_id in doc_ids) if oid is not None]
    if not oids:
        return {}
    return {str(document["_id"]): document
            for document in _collection().find({"_id": {"$in": oids}})}


def get_active_document() -> Optional[Dict]:
    """
    The most recently ingested PDF, or None if nothing is ingested.

    The fallback for a command given neither a document nor a session. A session's own
    PDF -- see sessions.py -- always takes precedence over this.
    """
    return _collection().find_one(sort=[("uploaded_at", -1)])


def resolve_document(reference: str) -> Optional[Dict]:
    """
    Find a document by id, exact filename, or a unique filename fragment.

    Typing an ObjectId by hand is miserable, so the CLI accepts `--doc constitution` and
    this resolves it. A fragment matching several documents is rejected rather than
    guessed at, so a command never silently targets the wrong PDF.
    """
    if not reference:
        return None

    document = get_document(reference)
    if document:
        return document

    exact = _collection().find_one({"filename": reference})
    if exact:
        return exact

    import re

    pattern = re.escape(reference)
    matches = list(_collection()
                   .find({"filename": {"$regex": pattern, "$options": "i"}})
                   .limit(5))
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        names = ", ".join(match["filename"] for match in matches)
        raise ValueError(f"{reference!r} matches several documents: {names}")
    return None
