"""
The answer cache's decision log.

    {ts, doc_id, event: lookup|store|invalidate, outcome, sim, verifier, latency_ms,
     entry_id, n_candidates}

Every lookup is logged, hits and misses alike, with *why* it missed -- nothing cached for
this document, nearest question below the similarity threshold, or vetoed by the verifier.
That breakdown is what makes the threshold tunable from real traffic, and it is the hit rate
the analytics page and the confusion heatmap report.

No user id, no session id and no question text: the log says how the cache behaved, not
who asked what. A TTL index expires rows after CACHE_EVENTS_TTL_DAYS.
"""

from datetime import datetime, timedelta, timezone
from typing import Dict, Optional

from .. import config
from .ids import as_object_id
from .mongo import get_db


def _collection():
    return get_db()[config.COLL_CACHE_EVENTS]


def log_event(event: str, outcome: str, doc_id=None, sim: Optional[float] = None,
              verifier: Optional[float] = None, latency_ms: Optional[int] = None,
              entry_id: Optional[str] = None, n_candidates: Optional[int] = None) -> None:
    """Append one decision. Never raises: the log must not be able to fail a turn."""
    try:
        _collection().insert_one({
            "ts": datetime.now(timezone.utc),
            "doc_id": as_object_id(doc_id) if doc_id is not None else None,
            "event": event,
            "outcome": outcome,
            "sim": None if sim is None else round(float(sim), 4),
            "verifier": None if verifier is None else round(float(verifier), 4),
            "latency_ms": latency_ms,
            "entry_id": entry_id,
            "n_candidates": n_candidates,
        })
    except Exception:
        pass


def hit_rate(doc_id=None, days: Optional[int] = None) -> Dict:
    """Lookups, hits and the miss breakdown, for one document or overall."""
    match: Dict = {"event": "lookup"}
    if doc_id is not None:
        match["doc_id"] = as_object_id(doc_id)
    if days:
        match["ts"] = {"$gte": datetime.now(timezone.utc) - timedelta(days=days)}
    rows = list(_collection().aggregate([
        {"$match": match},
        {"$group": {"_id": "$outcome", "n": {"$sum": 1},
                    "latency": {"$avg": "$latency_ms"}}},
    ]))
    by_outcome = {row["_id"]: row["n"] for row in rows}
    lookups = sum(by_outcome.values())
    hits = by_outcome.get("hit", 0)
    return {
        "lookups": lookups,
        "hits": hits,
        "hit_rate": round(hits / lookups, 4) if lookups else None,
        "outcomes": by_outcome,
    }
