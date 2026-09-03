"""
Per-document BM25 corpus in Mongo.

One row per chunk, keyed by (doc_id, page_number, chunk_index) — the same identity the
vector store uses — so a chunk appearing in both ANN and BM25 lists can be deduped.
"""

from __future__ import annotations

from typing import List, Optional

from langchain_core.documents import Document

from .. import config
from .ids import as_object_id
from .mongo import get_db


# In-process Okapi index, keyed by str(doc_id). Rebuilding from chunk text on every
# retrieve was wasted work; ingest (index_documents / delete_for) drops the entry.
_OKAPI_CACHE = {}


def _collection():
    return get_db()[config.COLL_BM25]


def chunk_key(page_number, chunk_index) -> str:
    return f"{page_number}:{chunk_index}"


def delete_for(doc_id) -> None:
    oid = as_object_id(doc_id)
    if oid is None:
        return
    invalidate_cache(oid)
    _collection().delete_many({"doc_id": oid})


def index_documents(doc_id, documents: List[Document]) -> int:
    """Replace this document's BM25 rows with the chunks just embedded."""
    oid = as_object_id(doc_id)
    if oid is None:
        return 0
    delete_for(oid)
    rows = []
    for doc in documents:
        meta = doc.metadata or {}
        page = meta.get("page_number")
        index = meta.get("chunk_index")
        text = doc.page_content or ""
        if page is None or index is None or not text.strip():
            continue
        rows.append({
            "doc_id": oid,
            "chunk_id": chunk_key(page, index),
            "page_number": page,
            "chunk_index": index,
            "filename": meta.get("filename") or meta.get("source") or "",
            "text": text,
        })
    if rows:
        _collection().insert_many(rows)
    return len(rows)


def load_documents(doc_id) -> List[Document]:
    """LangChain Documents in reading order, or [] if this PDF was ingested before BM25."""
    oid = as_object_id(doc_id)
    if oid is None:
        return []
    rows = list(_collection().find({"doc_id": oid}).sort(
        [("page_number", 1), ("chunk_index", 1)]))
    out = []
    for row in rows:
        out.append(Document(
            page_content=row.get("text") or "",
            metadata={
                "chunk_id": row.get("chunk_id") or chunk_key(
                    row.get("page_number"), row.get("chunk_index")),
                "doc_id": str(row.get("doc_id") or ""),
                "page_number": row.get("page_number"),
                "chunk_index": row.get("chunk_index"),
                "filename": row.get("filename") or "",
                "retrieval_source": "bm25",
            },
        ))
    return out


def ensure_index(doc_id) -> List[Document]:
    """
    Return the BM25 corpus, building it from the vector store when an older document
    has chunks in Qdrant/Mongo but no sidecar yet.
    """
    existing = load_documents(doc_id)
    if existing:
        return existing
    from .vectors import get_vector_store

    try:
        borrowed = get_vector_store().chunks_for(doc_id)
    except Exception:
        return []
    if borrowed:
        index_documents(doc_id, borrowed)
        return load_documents(doc_id)
    return []


def invalidate_cache(doc_id) -> None:
    """Drop the in-memory Okapi index so the next retrieve rebuilds from Mongo."""
    if doc_id is None:
        return
    _OKAPI_CACHE.pop(str(as_object_id(doc_id) or doc_id), None)
    _OKAPI_CACHE.pop(str(doc_id), None)


def get_okapi(doc_id):
    """
    Cached (BM25Okapi, documents) for this PDF, or (None, []).

    Documents are word-tokenised once. Passing raw strings into BM25Okapi treated each
    character as a term, so lexical hits almost never matched the query tokens.
    """
    oid = as_object_id(doc_id)
    key = str(oid or doc_id)
    hit = _OKAPI_CACHE.get(key)
    if hit is not None:
        return hit
    docs = ensure_index(doc_id)
    if not docs:
        return None, []
    from ..retrieval.bm25 import BM25Okapi, tokenize

    index = BM25Okapi([tokenize(doc.page_content) for doc in docs])
    pair = (index, docs)
    _OKAPI_CACHE[key] = pair
    return pair
