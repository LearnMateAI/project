"""
Generated resources: MCQs, practice questions, key points and summaries.

Stored with the **full attempt trail**, not just the accepted output. A resource that
needed a retry, and what the judge objected to the first time, is the data that says
whether the threshold is set anywhere near right -- and that question is unanswerable
after the fact if only the winner is kept.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from bson import ObjectId

from .. import config
from .ids import as_object_id
from .mongo import get_db


def _collection():
    return get_db()[config.COLL_RESOURCES]


def save_resource(doc_id, task: str, content: Any, accepted: bool,
                  attempts: List[Dict], verdict: Optional[Dict] = None,
                  source_preview: str = "", params: Optional[Dict] = None,
                  user_id: str = None) -> ObjectId:
    """
    Store one generated resource and return its id.

    `user_id` is who asked for it. It is written here rather than stamped on afterwards
    because a listing query filters on it: a record that exists for even a moment without
    an owner is a record another user's listing could return.
    """
    record = {
        "doc_id": as_object_id(doc_id),
        "user_id": str(user_id) if user_id else None,
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
    return _collection().insert_one(record).inserted_id


def get_resource(resource_id) -> Optional[Dict]:
    """One resource by id."""
    return _collection().find_one({"_id": as_object_id(resource_id)})


def list_resources(doc_id=None, task: str = None, accepted_only: bool = False,
                   limit: int = 25, user_id: str = None) -> List[Dict]:
    """
    Most recent resources first, filtered by document, task and/or owner.

    `accepted_only` is off by default on purpose: a rejected resource is still stored and
    still worth looking at, and hiding it would make the failure rate invisible.

    `user_id` is what the API always passes. Filtering by document alone would show one
    student the questions another student generated from the same shared PDF.
    """
    query: Dict[str, Any] = {}
    if doc_id is not None:
        query["doc_id"] = as_object_id(doc_id)
    if task:
        query["task"] = task
    if accepted_only:
        query["accepted"] = True
    if user_id is not None:
        query["user_id"] = str(user_id)

    return list(_collection().find(query).sort("created_at", -1).limit(limit))


def delete_resource(resource_id, user_id: str = None) -> bool:
    """
    Remove one resource. Returns False when it does not exist or is not this user's.

    The owner check is part of the query rather than a lookup followed by a delete, so
    there is no window in which the two could disagree.
    """
    query: Dict[str, Any] = {"_id": as_object_id(resource_id)}
    if user_id is not None:
        query["user_id"] = str(user_id)
    return _collection().delete_one(query).deleted_count > 0


def count_by_task(user_id: str) -> Dict[str, int]:
    """How many resources of each type this user has generated. For the analytics page."""
    pipeline = [
        {"$match": {"user_id": str(user_id)}},
        {"$group": {"_id": "$task", "n": {"$sum": 1},
                    "accepted": {"$sum": {"$cond": ["$accepted", 1, 0]}}}},
    ]
    return {row["_id"]: {"total": row["n"], "accepted": row["accepted"]}
            for row in _collection().aggregate(pipeline)}
