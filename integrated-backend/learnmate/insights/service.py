"""
The confusion heatmap for one document: compute, cache, return.

    chat_turns --(aggregate.py: Mongo pipelines)--> rows + per-page counts
               --(cluster.py: MiniLM + HDBSCAN + c-TF-IDF)--> topics
               --(confusion.py: signals, score, k-anonymity)--> pages + topics
               --> doc_insights (cached until new questions or INSIGHTS_TTL_S)

Aggregated across every student who has the document -- documents are shared by content
hash, so "the class" is everyone who uploaded the same notes -- and returned only in
aggregate: page counts, topic keywords, shares. No question text and no user id ever
leaves this module.
"""

import time
from datetime import datetime, timezone
from typing import Dict

from .. import config
from . import aggregate, cluster, confusion


def _n_pages(doc_id, stats_pages) -> int:
    from ..storage import pdf_store

    document = pdf_store.get_document(doc_id) or {}
    seen = [row["page"] for row in stats_pages if isinstance(row.get("page"), int)]
    return max([int(document.get("n_pages") or 0)] + seen)


def compute_heatmap(doc_id, rows=None, stats=None, n_pages: int = None) -> Dict:
    """
    Build the heatmap. `rows`/`stats`/`n_pages` may be passed in (the evaluation harness
    does, with synthetic logs); otherwise they are read from MongoDB.
    """
    timings = {}
    started = time.perf_counter()
    if rows is None:
        rows = aggregate.question_rows(doc_id)
    if stats is None:
        stats = aggregate.page_stats(doc_id, config.INSIGHTS_LOW_SCORE)
    timings["aggregate_ms"] = int((time.perf_counter() - started) * 1000)
    k = config.INSIGHTS_MIN_USERS
    weights = confusion.parse_weights(config.INSIGHTS_WEIGHTS)

    labels = [-1] * len(rows)
    terms: Dict[int, list] = {}
    if len(rows) >= config.INSIGHTS_MIN_QUESTIONS:
        clock = time.perf_counter()
        vectors = cluster.embed([row["question"] for row in rows])
        timings["embed_ms"] = int((time.perf_counter() - clock) * 1000)
        clock = time.perf_counter()
        labels = [int(label) for label in cluster.cluster(
            vectors, config.INSIGHTS_MIN_CLUSTER, config.INSIGHTS_MIN_SAMPLES)]
        timings["cluster_ms"] = int((time.perf_counter() - clock) * 1000)
        clock = time.perf_counter()
        groups: Dict[int, list] = {}
        for row, label in zip(rows, labels):
            if label != -1:
                groups.setdefault(label, []).append(row["question"])
        terms = cluster.ctfidf(groups)
        timings["label_ms"] = int((time.perf_counter() - clock) * 1000)

    repeats = confusion.repeat_flags(rows, labels, config.INSIGHTS_REPEAT_DAYS)
    repeats_by_page: Dict[int, int] = {}
    for row, repeat in zip(rows, repeats):
        if repeat and row.get("page") is not None:
            repeats_by_page[int(row["page"])] = repeats_by_page.get(int(row["page"]), 0) + 1

    pages = confusion.page_confusion(stats["pages"], repeats_by_page,
                                     n_pages if n_pages is not None
                                     else _n_pages(doc_id, stats["pages"]),
                                     weights, k)
    topics = confusion.topic_summary(rows, labels, terms, repeats, weights, k,
                                     config.INSIGHTS_LOW_SCORE)
    totals = stats.get("totals") or {}
    timings["total_ms"] = int((time.perf_counter() - started) * 1000)
    return {
        "doc_id": str(doc_id),
        "computed_at": datetime.now(timezone.utc).isoformat(),
        "n_questions": totals.get("questions", len(rows)),
        "n_users": totals.get("distinct_users"),
        "unattributed": totals.get("unattributed", 0),
        "k": k,
        "weights": weights,
        "pages": pages,
        **topics,
        "timings": timings,
        # Returned to the evaluation harness, never serialised to the API (see get_heatmap).
        "_labels": labels,
    }


def _public(result: Dict) -> Dict:
    return {key: value for key, value in result.items() if not key.startswith("_")}


def get_heatmap(doc_id, refresh: bool = False) -> Dict:
    """The cached heatmap, recomputed when questions have arrived or it has gone stale."""
    from ..storage import cache_events
    from ..storage.ids import as_object_id
    from ..storage.mongo import get_db

    database = get_db()
    oid = as_object_id(doc_id)
    source_count = database[config.COLL_CHAT_TURNS].count_documents(
        {"doc_id": oid, "role": "assistant"})
    cached = database[config.COLL_DOC_INSIGHTS].find_one({"_id": oid})
    fresh = (cached and not refresh and cached.get("source_count") == source_count
             and time.time() - cached.get("computed_ts", 0) < config.INSIGHTS_TTL_S)
    if fresh:
        result = cached["result"]
    else:
        result = _public(compute_heatmap(doc_id))
        database[config.COLL_DOC_INSIGHTS].replace_one(
            {"_id": oid},
            {"_id": oid, "source_count": source_count, "computed_ts": time.time(),
             "result": result},
            upsert=True)
    try:
        cache = cache_events.hit_rate(doc_id)
    except Exception:
        cache = None
    return {**result, "answer_cache": cache, "from_cache": bool(fresh)}
