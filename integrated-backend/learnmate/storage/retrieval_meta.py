"""
Corpus-level statistics the sparse index depends on.

    {_id: "bm25", avgdl, analyzer_version, n_chunks, updated_at}

BM25's length normalisation divides by the average chunk length, and that number is baked
into every document vector at ingest. It therefore has to be *one* number for the whole
collection and stable across processes: two documents ingested against different averages
would be scored on different scales. It is computed once -- by scripts/reindex_qdrant.py
over the whole corpus, or from the first document ingested into an empty index -- and read
back from here afterwards.

Drift is tolerated rather than chased. Recomputing it as documents arrive would mean
rewriting every existing vector; BM25 is insensitive to a modest error in avgdl, and
LEARNMATE_BM25_AVGDL pins it outright when an evaluation needs it fixed.
"""

from datetime import datetime, timezone
from typing import Optional, Sequence

from .. import config
from .mongo import get_db

COLL_RETRIEVAL_META = "retrieval_meta"
_BM25_KEY = "bm25"


def _collection():
    return get_db()[COLL_RETRIEVAL_META]


def get_bm25_meta() -> Optional[dict]:
    try:
        return _collection().find_one({"_id": _BM25_KEY})
    except Exception:
        return None


def set_bm25_meta(avgdl: float, n_chunks: int, analyzer_version: str) -> None:
    _collection().update_one(
        {"_id": _BM25_KEY},
        {"$set": {"avgdl": float(avgdl), "n_chunks": int(n_chunks),
                  "analyzer_version": analyzer_version,
                  "updated_at": datetime.now(timezone.utc)}},
        upsert=True,
    )


def resolve_avgdl(texts: Sequence[str] = ()) -> float:
    """
    The avgdl to index `texts` with.

    Pinned by config if set; otherwise the stored corpus value; otherwise measured from
    `texts` and stored, so the first document into an empty index sets the scale for the
    rest. Falls back to 100 terms only when there is nothing at all to measure.
    """
    if config.BM25_AVGDL > 0:
        return config.BM25_AVGDL

    meta = get_bm25_meta()
    if meta and meta.get("avgdl"):
        return float(meta["avgdl"])

    from ..retrieval.sparse import ANALYZER_VERSION, mean_doc_length

    measured = mean_doc_length(texts)
    if measured <= 0:
        return 100.0
    try:
        set_bm25_meta(measured, len(texts), ANALYZER_VERSION)
    except Exception:
        # A read-only or unreachable Mongo must not stop an ingest; the next one retries.
        pass
    return measured
