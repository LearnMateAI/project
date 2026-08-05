"""
Vector-store selection.

Two interchangeable backends implement the same LangChain VectorStore surface, so nothing
upstream -- ingestion, retrieval, the chat graph -- knows or cares which is configured:

    qdrant    a Qdrant server. Real HNSW index, filtering and scoring server-side.
    mongodb   the same MongoDB that holds everything else. Atlas $vectorSearch where
              available, exact NumPy scoring otherwise.

Both return raw cosine similarity in [-1, 1], so RELEVANCE_THRESHOLD carries the same
meaning either way and a corpus can be re-ingested into the other backend without
retuning anything.

Note that switching backends does not migrate existing vectors. Re-run
`ingest_pdf(<pdf>, force=True)` to populate the new one; the PDFs and page text are
in MongoDB and are not affected.
"""

from typing import Optional

from langchain_core.vectorstores import VectorStore

from .. import config

_STORE: Optional[VectorStore] = None


def build_vector_store(backend: str = None) -> VectorStore:
    """Construct the configured vector store without caching it."""
    backend = (backend or config.VECTOR_BACKEND).lower()

    if backend == "qdrant":
        from .qdrant_vectors import QdrantVectorStore
        return QdrantVectorStore()

    if backend in ("mongodb", "mongo"):
        from .mongo_vectors import MongoVectorStore
        return MongoVectorStore()

    raise ValueError(
        f"Unknown LEARNMATE_VECTOR_BACKEND {backend!r}; expected 'qdrant' or 'mongodb'."
    )


def get_vector_store() -> VectorStore:
    """Process-wide vector store."""
    global _STORE
    if _STORE is None:
        _STORE = build_vector_store()
    return _STORE


def reset_vector_store() -> None:
    """Drop the cached store, so a changed backend takes effect. Used by tests."""
    global _STORE
    _STORE = None
