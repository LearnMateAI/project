"""
Persistence for everything the agents produce: generated resources, evaluation verdicts
and chat history.

Generated content is stored with the full attempt trail, not just the accepted output.
A resource that needed a retry, and what the judge objected to the first time, is the
data that says whether the threshold is set anywhere near right -- and that question is
unanswerable after the fact if only the winner is kept.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union

from bson import ObjectId
from bson.errors import InvalidId

from .. import config
from .mongo import get_db


def _as_object_id(value):
    if isinstance(value, ObjectId) or value is None:
        return value
    try:
        return ObjectId(str(value))
    except (InvalidId, TypeError):
        return value


# --- Generated resources -------------------------------------------------------------

def save_resource(doc_id, task: str, content: Any, accepted: bool,
                  attempts: List[Dict], verdict: Optional[Dict] = None,
                  source_preview: str = "", params: Optional[Dict] = None) -> ObjectId:
    """Store one generated resource and return its id."""
    record = {
        "doc_id": _as_object_id(doc_id),
        "task": task,
        "content": content,
        "accepted": accepted,
        "score": (verdict or {}).get("score"),
        "threshold": (verdict or {}).get("threshold", config.EVALUATOR_THRESHOLD),
        "verdict": verdict,
        "attempts": attempts,
        "n_attempts": len(attempts),
        # Enough of the source to see what the model was working from, without storing a
        # second copy of the document inside every resource.
        "source_preview": (source_preview or "")[:1000],
        "params": params or {},
        "created_at": datetime.now(timezone.utc),
    }
    return get_db()[config.COLL_RESOURCES].insert_one(record).inserted_id


def get_resource(resource_id) -> Optional[Dict]:
    return get_db()[config.COLL_RESOURCES].find_one({"_id": _as_object_id(resource_id)})


def list_resources(doc_id=None, task: str = None, accepted_only: bool = False,
                   limit: int = 25) -> List[Dict]:
    """Most recent resources first, filtered by document and/or task."""
    query: Dict[str, Any] = {}
    if doc_id is not None:
        query["doc_id"] = _as_object_id(doc_id)
    if task:
        query["task"] = task
    if accepted_only:
        query["accepted"] = True

    return list(get_db()[config.COLL_RESOURCES]
                .find(query)
                .sort("created_at", -1)
                .limit(limit))


# --- Evaluation log ------------------------------------------------------------------

def log_evaluation(task: str, attempt: int, score, passed: bool, threshold: int,
                   stage: str = "judge", elapsed: float = None,
                   doc_id=None, extra: Optional[Dict] = None) -> None:
    """
    Record one verdict.

    stage -- "validator" when structural checks rejected the content without the judge
             running, "judge" when the model scored it, "parse" when the generator's
             output could not be read at all. Keeping all three makes it answerable how
             often the cheap gate is doing the work.

    Never raises: logging must not be able to take down a generation run.
    """
    record = {
        "task": task,
        "attempt": attempt,
        "stage": stage,
        "score": score,
        "passed": bool(passed),
        "threshold": threshold,
        "doc_id": _as_object_id(doc_id),
        "created_at": datetime.now(timezone.utc),
    }
    if elapsed is not None:
        record["elapsed_s"] = round(elapsed, 2)
    if extra:
        record.update(extra)

    try:
        get_db()[config.COLL_EVALUATIONS].insert_one(record)
    except Exception:
        pass


def evaluation_stats() -> Dict[str, Dict]:
    """
    Score distribution per task, for deciding whether the threshold is meaningful.

    A judge whose scores cluster in a narrow band cannot separate good from bad at any
    threshold, however it is set, and `distinct` is what exposes that.
    """
    pipeline = [
        {"$match": {"stage": "judge", "score": {"$type": "number"}}},
        {"$group": {
            "_id": "$task",
            "n": {"$sum": 1},
            "min": {"$min": "$score"},
            "max": {"$max": "$score"},
            "avg": {"$avg": "$score"},
            "scores": {"$push": "$score"},
            "passes": {"$sum": {"$cond": ["$passed", 1, 0]}},
        }},
        {"$sort": {"_id": 1}},
    ]

    out = {}
    for row in get_db()[config.COLL_EVALUATIONS].aggregate(pipeline):
        scores = sorted(row["scores"])
        out[row["_id"]] = {
            "n": row["n"],
            "min": row["min"],
            "median": scores[len(scores) // 2],
            "max": row["max"],
            "mean": round(row["avg"], 1),
            "distinct": len(set(scores)),
            "pass_rate": round(row["passes"] / row["n"], 3),
        }
    return out


def stage_counts() -> Dict[str, int]:
    """How many evaluations each gate decided -- parse, validator or judge."""
    pipeline = [{"$group": {"_id": "$stage", "n": {"$sum": 1}}}]
    return {row["_id"]: row["n"]
            for row in get_db()[config.COLL_EVALUATIONS].aggregate(pipeline)}


# --- Chat history --------------------------------------------------------------------

def save_turn(session_id: str, role: str, content: str, doc_id=None,
              meta: Optional[Dict] = None) -> None:
    """Append one chat turn."""
    get_db()[config.COLL_CHAT_TURNS].insert_one({
        "session_id": session_id,
        "role": role,
        "content": content,
        "doc_id": _as_object_id(doc_id),
        "meta": meta or {},
        "created_at": datetime.now(timezone.utc),
    })


def load_history(session_id: str, max_turns: int = None) -> List[Dict[str, str]]:
    """
    The last N user+assistant pairs, oldest first.

    Fetched newest-first then reversed: with an index on (session_id, created_at) that is
    a bounded scan, where sorting the whole session forward and taking the tail is not.
    """
    max_turns = max_turns or config.MAX_HISTORY_TURNS
    rows = list(get_db()[config.COLL_CHAT_TURNS]
                .find({"session_id": session_id}, {"role": 1, "content": 1})
                .sort("created_at", -1)
                .limit(max_turns * 2))
    rows.reverse()
    return [{"role": row["role"], "content": row["content"]} for row in rows]


def clear_history(session_id: str) -> int:
    """Forget a session. Returns how many turns were removed."""
    return get_db()[config.COLL_CHAT_TURNS].delete_many(
        {"session_id": session_id}).deleted_count


def list_sessions(limit: int = 20) -> List[Dict]:
    """Known chat sessions, most recently active first."""
    pipeline = [
        {"$group": {"_id": "$session_id", "turns": {"$sum": 1},
                    "last": {"$max": "$created_at"}}},
        {"$sort": {"last": -1}},
        {"$limit": limit},
    ]
    return list(get_db()[config.COLL_CHAT_TURNS].aggregate(pipeline))
