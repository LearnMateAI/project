"""
PDF storage in MongoDB GridFS.

An uploaded PDF is kept whole, in the database, alongside the chunks derived from it, so
a document can be re-read, re-chunked or handed back to a user without depending on the
uploader's filesystem.

Identity is the SHA-256 of the file bytes, not the filename. Uploading the same PDF twice
under different names is recognised as one document, which keeps the embedding work from
being repeated and gives every stored resource a stable document to point at.

Retrieval is by indexed _id or sha256, so fetching a document's metadata is a single
indexed lookup and fetching its bytes is a GridFS read by id.
"""

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Union

import gridfs
from bson import ObjectId
from bson.errors import InvalidId

from .. import config
from .mongo import get_db


def _bucket():
    return gridfs.GridFSBucket(get_db(), bucket_name=config.GRIDFS_BUCKET)


def _coerce_id(doc_id: Union[str, ObjectId]) -> Optional[ObjectId]:
    """Accept an ObjectId or its hex string; return None if it is neither."""
    if isinstance(doc_id, ObjectId):
        return doc_id
    try:
        return ObjectId(str(doc_id))
    except (InvalidId, TypeError):
        return None


def store_pdf(source: Union[str, Path, bytes], filename: str = None) -> Dict:
    """
    Store a PDF and return its document record.

    `source` is a path or the raw bytes, so this serves both a CLI path argument and an
    HTTP upload without the caller staging a temp file.

    A PDF already present is returned untouched with `existing` set, letting the ingestion
    pipeline skip re-embedding work that has already been done.
    """
    if isinstance(source, (str, Path)):
        path = Path(source)
        if not path.exists():
            raise FileNotFoundError(f"No such PDF: {path}")
        data = path.read_bytes()
        filename = filename or path.name
    else:
        data = bytes(source)
        filename = filename or "upload.pdf"

    if not data:
        raise ValueError("Refusing to store an empty file.")

    digest = hashlib.sha256(data).hexdigest()
    documents = get_db()[config.COLL_DOCUMENTS]

    existing = documents.find_one({"sha256": digest})
    if existing:
        existing["existing"] = True
        return existing

    gridfs_id = _bucket().upload_from_stream(
        filename, data, metadata={"sha256": digest, "content_type": "application/pdf"})

    record = {
        "filename": filename,
        "sha256": digest,
        "size_bytes": len(data),
        "gridfs_id": gridfs_id,
        "uploaded_at": datetime.now(timezone.utc),
        # Filled in by the ingestion pipeline once the text has been processed.
        "n_pages": None,
        "n_chunks": None,
        "ingested_at": None,
    }
    record["_id"] = documents.insert_one(record).inserted_id
    record["existing"] = False
    return record


def get_document(doc_id: Union[str, ObjectId]) -> Optional[Dict]:
    """Look up one document's metadata by id."""
    oid = _coerce_id(doc_id)
    if oid is None:
        return None
    return get_db()[config.COLL_DOCUMENTS].find_one({"_id": oid})


def find_by_hash(digest: str) -> Optional[Dict]:
    """Look up a document by the SHA-256 of its bytes."""
    return get_db()[config.COLL_DOCUMENTS].find_one({"sha256": digest})


def resolve_document(reference: str) -> Optional[Dict]:
    """
    Find a document by id, exact filename, or a unique filename fragment.

    Typing an ObjectId by hand is miserable, so the CLI accepts `--doc constitution`
    and this resolves it. A fragment matching several documents is rejected rather than
    guessed at, so a command never silently targets the wrong PDF.
    """
    if not reference:
        return None

    document = get_document(reference)
    if document:
        return document

    documents = get_db()[config.COLL_DOCUMENTS]
    exact = documents.find_one({"filename": reference})
    if exact:
        return exact

    import re

    pattern = re.escape(reference)
    matches = list(documents.find({"filename": {"$regex": pattern, "$options": "i"}}).limit(5))
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        names = ", ".join(match["filename"] for match in matches)
        raise ValueError(f"{reference!r} matches several documents: {names}")
    return None


def get_pdf_bytes(doc_id: Union[str, ObjectId]) -> Optional[bytes]:
    """Read a stored PDF back out of GridFS."""
    document = get_document(doc_id)
    if not document or not document.get("gridfs_id"):
        return None
    stream = _bucket().open_download_stream(document["gridfs_id"])
    try:
        return stream.read()
    finally:
        stream.close()


def export_pdf(doc_id: Union[str, ObjectId], destination: Union[str, Path]) -> Path:
    """Write a stored PDF back to disk."""
    data = get_pdf_bytes(doc_id)
    if data is None:
        raise KeyError(f"No stored PDF for document {doc_id}")

    destination = Path(destination)
    if destination.is_dir():
        document = get_document(doc_id)
        destination = destination / document["filename"]
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(data)
    return destination


def list_documents(limit: int = 50) -> List[Dict]:
    """Most recently uploaded documents first."""
    return list(get_db()[config.COLL_DOCUMENTS]
                .find()
                .sort("uploaded_at", -1)
                .limit(limit))


def store_pages(doc_id: Union[str, ObjectId], pages: List[Dict]) -> int:
    """
    Store the cleaned text of every page.

    Kept separately from the chunks because the two answer different questions. Chunks are
    sized and overlapped for retrieval, so reassembling a page from them repeats text at
    every boundary and starts mid-sentence. Resource generation wants the page as it reads,
    and a page is also the natural unit for `--pages 12-18`.
    """
    from pymongo import UpdateOne

    oid = _coerce_id(doc_id)
    operations = [
        UpdateOne(
            {"doc_id": oid, "page_number": page["page_number"]},
            {"$set": {"doc_id": oid,
                      "page_number": page["page_number"],
                      "page_index": page["page_index"],
                      "text": page["page_content"]}},
            upsert=True,
        )
        for page in pages
    ]
    if not operations:
        return 0
    get_db()[config.COLL_PAGES].bulk_write(operations, ordered=False)
    return len(operations)


def delete_pages(doc_id: Union[str, ObjectId]) -> int:
    """Drop a document's stored page text. Returns how many pages were removed."""
    return get_db()[config.COLL_PAGES].delete_many(
        {"doc_id": _coerce_id(doc_id)}).deleted_count


def get_pages(doc_id: Union[str, ObjectId], page_numbers: Optional[List[int]] = None
              ) -> List[Dict]:
    """Cleaned page text in reading order, optionally only the pages named."""
    query: Dict = {"doc_id": _coerce_id(doc_id)}
    if page_numbers:
        query["page_number"] = {"$in": list(page_numbers)}
    return list(get_db()[config.COLL_PAGES]
                .find(query, {"page_number": 1, "text": 1})
                .sort("page_number", 1))


def mark_ingested(doc_id: Union[str, ObjectId], n_pages: int, n_chunks: int) -> None:
    """Record the outcome of ingestion on the document record."""
    oid = _coerce_id(doc_id)
    get_db()[config.COLL_DOCUMENTS].update_one(
        {"_id": oid},
        {"$set": {"n_pages": n_pages, "n_chunks": n_chunks,
                  "ingested_at": datetime.now(timezone.utc)}},
    )


def delete_document(doc_id: Union[str, ObjectId]) -> bool:
    """Remove a document, its stored PDF and every chunk derived from it."""
    document = get_document(doc_id)
    if not document:
        return False

    database = get_db()
    database[config.COLL_CHUNKS].delete_many({"doc_id": document["_id"]})
    database[config.COLL_PAGES].delete_many({"doc_id": document["_id"]})
    if document.get("gridfs_id"):
        try:
            _bucket().delete(document["gridfs_id"])
        except gridfs.NoFile:
            pass
    database[config.COLL_DOCUMENTS].delete_one({"_id": document["_id"]})
    return True
