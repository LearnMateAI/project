"""
MongoDB aggregation pipelines over the chat log of one document.

Two pipelines, both run server-side so only rows or aggregates cross the wire:

    question_rows_pipeline   one row per answered question: who asked (as an opaque id),
                             what, when, which page it landed on, and how it went
    page_stats_pipeline      per-page counts via $facet/$group -- questions, distinct
                             students, and how many were answered from general knowledge,
                             low-scored, rejected, or served from the answer cache

Every chat turn is stored as its own row, so pairing a question with its answer is a window
function: `$setWindowFields` partitioned by session and ordered by time, with `$shift` to
read the row before. New turns also carry the question on the answer row (see
chat_agent/persist.py); older ones do not, and the window covers them.

Which page a question "is about":

    pdf mode      the first citation -- the best chunk after reranking
    general mode  retrieval's nearest chunk (meta.retrieval.top_page), even though it was
                  not good enough to answer from. "Nothing on this page answered the
                  question it was nearest to" is exactly the signal a heatmap wants.
"""

from typing import Dict, List

from .. import config


def _row_stages(doc_oid) -> List[Dict]:
    return [
        {"$match": {"doc_id": doc_oid}},
        {"$setWindowFields": {
            "partitionBy": "$session_id",
            "sortBy": {"created_at": 1},
            "output": {
                "prev_content": {"$shift": {"output": "$content", "by": -1}},
                "prev_role": {"$shift": {"output": "$role", "by": -1}},
            },
        }},
        {"$match": {"role": "assistant"}},
        {"$project": {
            "_id": 0,
            "user_id": 1,
            "created_at": 1,
            "question": {"$ifNull": [
                "$meta.standalone_query",
                {"$ifNull": ["$meta.question",
                             {"$cond": [{"$eq": ["$prev_role", "user"]},
                                        "$prev_content", None]}]}]},
            "mode": "$meta.mode",
            "score": "$meta.score",
            "accepted": "$meta.accepted",
            "page": {"$ifNull": [{"$arrayElemAt": ["$meta.citations.page", 0]},
                                 "$meta.retrieval.top_page"]},
            "cache_hit": {"$ifNull": ["$meta.cache.hit", False]},
        }},
        {"$match": {"question": {"$nin": [None, ""]}}},
    ]


def question_rows_pipeline(doc_oid) -> List[Dict]:
    return _row_stages(doc_oid) + [{"$sort": {"created_at": 1}}]


def page_stats_pipeline(doc_oid, low_score: int) -> List[Dict]:
    """Per-page aggregates. `low` and `rejected` count only turns the judge scored."""
    # A gated or unjudged turn stores score None; only a number means the judge ran.
    judged_any = {"$in": [{"$type": "$score"}, ["int", "long", "double"]]}
    return _row_stages(doc_oid) + [
        {"$facet": {
            "pages": [
                {"$match": {"page": {"$ne": None}}},
                {"$group": {
                    "_id": "$page",
                    "questions": {"$sum": 1},
                    "users": {"$addToSet": "$user_id"},
                    "general": {"$sum": {"$cond": [{"$eq": ["$mode", "general"]}, 1, 0]}},
                    "judged": {"$sum": {"$cond": [judged_any, 1, 0]}},
                    "low": {"$sum": {"$cond": [
                        {"$and": [judged_any, {"$lt": ["$score", low_score]}]}, 1, 0]}},
                    "rejected": {"$sum": {"$cond": [
                        {"$and": [judged_any, {"$eq": ["$accepted", False]}]}, 1, 0]}},
                    "cache_hits": {"$sum": {"$cond": ["$cache_hit", 1, 0]}},
                }},
                {"$project": {"_id": 0, "page": "$_id", "questions": 1, "general": 1,
                              "judged": 1, "low": 1, "rejected": 1, "cache_hits": 1,
                              "distinct_users": {"$size": "$users"}}},
                {"$sort": {"page": 1}},
            ],
            "totals": [
                {"$group": {"_id": None, "questions": {"$sum": 1},
                            "users": {"$addToSet": "$user_id"},
                            "unattributed": {"$sum": {"$cond": [
                                {"$eq": ["$page", None]}, 1, 0]}}}},
                {"$project": {"_id": 0, "questions": 1, "unattributed": 1,
                              "distinct_users": {"$size": "$users"}}},
            ],
        }},
    ]


def question_rows(doc_id) -> List[Dict]:
    from ..storage.ids import as_object_id
    from ..storage.mongo import get_db

    return list(get_db()[config.COLL_CHAT_TURNS].aggregate(
        question_rows_pipeline(as_object_id(doc_id))))


def page_stats(doc_id, low_score: int) -> Dict:
    from ..storage.ids import as_object_id
    from ..storage.mongo import get_db

    result = list(get_db()[config.COLL_CHAT_TURNS].aggregate(
        page_stats_pipeline(as_object_id(doc_id), low_score)))
    facet = result[0] if result else {"pages": [], "totals": []}
    totals = facet.get("totals") or [{}]
    return {"pages": facet.get("pages") or [],
            "totals": totals[0] if totals else {}}
