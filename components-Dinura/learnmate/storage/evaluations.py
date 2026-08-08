"""
The evaluation log, and the statistics read back off it.

Every verdict is recorded -- passes as well as failures -- so score distributions and
timings can be analysed afterwards rather than only failures being visible.

`stage` says which gate decided an attempt, and that is the more useful of the two
questions this collection answers:

    parse       the generator's output could not be read at all
    validator   structural checks rejected it without the judge running
    judge       the model scored it
    skipped     evaluation was switched off

If the validator is deciding most attempts, the generation prompt needs work, not the
threshold.
"""

from datetime import datetime, timezone
from typing import Dict, Optional

from .. import config
from .ids import as_object_id
from .mongo import get_db


def _collection():
    return get_db()[config.COLL_EVALUATIONS]


def log_evaluation(task: str, attempt: int, score, passed: bool, threshold: int,
                   stage: str = "judge", elapsed: float = None,
                   doc_id=None, extra: Optional[Dict] = None) -> None:
    """
    Record one verdict.

    Never raises: logging must not be able to take down a generation run. A lost row is a
    gap in the statistics; an exception here would be a lost resource.
    """
    record = {
        "task": task,
        "attempt": attempt,
        "stage": stage,
        "score": score,
        "passed": bool(passed),
        "threshold": threshold,
        "doc_id": as_object_id(doc_id),
        "created_at": datetime.now(timezone.utc),
    }
    if elapsed is not None:
        record["elapsed_s"] = round(elapsed, 2)
    if extra:
        record.update(extra)

    try:
        _collection().insert_one(record)
    except Exception:
        pass


def evaluation_stats() -> Dict[str, Dict]:
    """
    Score distribution per task, for deciding whether the threshold is meaningful.

    A judge whose scores cluster in a narrow band cannot separate good from bad at any
    threshold, however it is set, and `distinct` is what exposes that. Only judge-stage
    rows are counted -- a validator rejection has no score to average.
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
    for row in _collection().aggregate(pipeline):
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
    """How many evaluations each gate decided -- parse, validator, judge or skipped."""
    pipeline = [{"$group": {"_id": "$stage", "n": {"$sum": 1}}}]
    return {row["_id"]: row["n"] for row in _collection().aggregate(pipeline)}
