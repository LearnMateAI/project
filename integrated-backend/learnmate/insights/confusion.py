"""
From counts to a confusion score, with k-anonymity. Pure functions: no Mongo, no models.

A page's confusion combines how much a class asks about it with four signs the answers
did not land:

    general    share of its questions the document could not answer (general mode --
               retrieval found nothing good enough on or near this page)
    low_score  share of judged answers the judge scored under the pass mark
    rejected   share of judged answers delivered below the pass mark after the retry
    repeat     share of questions that were the same student coming back to the same
               topic within INSIGHTS_REPEAT_DAYS -- the answer did not stick

    confusion(p) = volume(p) * (1 + sum_i w_i x_i(p)) / (1 + sum_i w_i)
    volume(p)    = questions(p) / max over shown pages of questions

so a heavily-asked page with no warning signs scores 1/(1+sum w) of one with every
sign, and a page nobody asks about scores 0 however its few answers went. The components
are returned alongside, because "why is this page red" matters more than the number.

k-anonymity: a page or topic with fewer than k distinct students is suppressed -- shown as
present, with no counts. With one student asking about page 12, "one question, answered
from general knowledge" describes that student.
"""

from collections import Counter, defaultdict
from datetime import datetime
from typing import Dict, List, Optional, Sequence

SIGNALS = ("general", "low_score", "rejected", "repeat")


def parse_weights(spec: str) -> Dict[str, float]:
    weights = {name: 1.0 for name in SIGNALS}
    for part in (spec or "").split(","):
        if "=" in part:
            name, value = part.split("=", 1)
            name = name.strip()
            if name in weights:
                try:
                    weights[name] = max(0.0, float(value))
                except ValueError:
                    pass
    return weights


def _seconds(later, earlier) -> Optional[float]:
    if isinstance(later, datetime) and isinstance(earlier, datetime):
        return (later - earlier).total_seconds()
    return None


def repeat_flags(rows: Sequence[Dict], labels: Sequence[int], days: int) -> List[bool]:
    """
    Per row: is this the same student returning to the same topic within `days`?

    Rows must be in time order. Noise (label -1) is never a repeat -- a question that fits
    no topic cannot recur within one.
    """
    last_seen: Dict = {}
    window = days * 86400
    flags = []
    for row, label in zip(rows, labels):
        repeat = False
        if label != -1:
            key = (row.get("user_id"), int(label))
            when = row.get("created_at")
            previous = last_seen.get(key)
            gap = _seconds(when, previous)
            repeat = gap is not None and 0 <= gap <= window
            last_seen[key] = when
        flags.append(repeat)
    return flags


def _score(signals: Dict[str, float], weights: Dict[str, float], volume: float) -> float:
    total = sum(weights.values())
    weighted = sum(weights[name] * signals.get(name, 0.0) for name in SIGNALS)
    return volume * (1.0 + weighted) / (1.0 + total)


def page_confusion(page_stats: Sequence[Dict], repeats_by_page: Dict[int, int],
                   n_pages: int, weights: Dict[str, float], k: int) -> List[Dict]:
    """One entry per page 1..n_pages, suppressed where fewer than k students contributed."""
    by_page = {int(row["page"]): row for row in page_stats if row.get("page") is not None}
    shown = [row["questions"] for row in by_page.values() if row["distinct_users"] >= k]
    max_n = max(shown) if shown else 0
    last = max([n_pages or 0] + list(by_page))

    pages = []
    for page in range(1, last + 1):
        row = by_page.get(page)
        if row is None:
            pages.append({"page": page, "questions": 0, "distinct_users": 0,
                          "confusion": 0.0, "suppressed": False, "signals": None})
            continue
        if row["distinct_users"] < k:
            pages.append({"page": page, "questions": None, "distinct_users": None,
                          "confusion": None, "suppressed": True, "signals": None})
            continue
        n = row["questions"]
        judged = row.get("judged") or 0
        signals = {
            "general": row.get("general", 0) / n,
            "low_score": (row.get("low", 0) / judged) if judged else 0.0,
            "rejected": (row.get("rejected", 0) / judged) if judged else 0.0,
            "repeat": repeats_by_page.get(page, 0) / n,
        }
        volume = n / max_n if max_n else 0.0
        pages.append({
            "page": page, "questions": n, "distinct_users": row["distinct_users"],
            "cache_hits": row.get("cache_hits", 0),
            "confusion": round(_score(signals, weights, volume), 4),
            "suppressed": False,
            "signals": {name: round(value, 4) for name, value in signals.items()},
        })
    return pages


def topic_summary(rows: Sequence[Dict], labels: Sequence[int], terms: Dict[int, List[str]],
                  repeats: Sequence[bool], weights: Dict[str, float], k: int,
                  low_score: int) -> Dict:
    """Topics with at least k students: keywords, size, pages, and the same four signals."""
    members = defaultdict(list)
    for index, label in enumerate(labels):
        if label != -1:
            members[int(label)].append(index)

    topics, suppressed = [], 0
    sizes = [len(idx) for idx in members.values()]
    max_size = max(sizes) if sizes else 0
    for label, indices in members.items():
        users = {rows[i].get("user_id") for i in indices}
        if len(users) < k:
            suppressed += 1
            continue
        n = len(indices)
        judged = [i for i in indices if isinstance(rows[i].get("score"), (int, float))]
        signals = {
            "general": sum(rows[i].get("mode") == "general" for i in indices) / n,
            "low_score": (sum(rows[i]["score"] < low_score for i in judged) / len(judged))
            if judged else 0.0,
            "rejected": (sum(rows[i].get("accepted") is False for i in judged) / len(judged))
            if judged else 0.0,
            "repeat": sum(repeats[i] for i in indices) / n,
        }
        pages = Counter(rows[i].get("page") for i in indices if rows[i].get("page") is not None)
        topics.append({
            "id": label,
            "terms": terms.get(label, []),
            "size": n,
            "distinct_users": len(users),
            "pages": [{"page": page, "share": round(count / n, 3)}
                      for page, count in pages.most_common(3)],
            "confusion": round(_score(signals, weights, n / max_size if max_size else 0), 4),
            "signals": {name: round(value, 4) for name, value in signals.items()},
        })
    topics.sort(key=lambda topic: (-topic["confusion"], -topic["size"]))
    clustered = sum(len(idx) for idx in members.values())
    return {"topics": topics, "suppressed_topics": suppressed,
            "clustered_share": round(clustered / len(labels), 4) if len(labels) else None}
