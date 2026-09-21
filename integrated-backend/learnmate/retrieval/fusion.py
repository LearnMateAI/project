"""
Rank fusion, computed in this process.

Qdrant fuses server-side (see storage/qdrant_vectors.QdrantVectorStore.query), and that is
the path the chat agent takes. These are the same two formulas in Python, for the places
Qdrant is not in the loop: the MongoDB vector backend, and the evaluation harness, which
checks that app-side and server-side fusion rank identically before trusting either.

    RRF    Cormack, Clarke & Buettcher (2009). score(d) = sum_i w_i / (k + rank_i(d)).
           Uses only ranks, so it needs no score calibration between retrievers -- which
           is exactly the problem with BM25 (unbounded) against cosine (-1..1).
    DBSF   Distribution-Based Score Fusion, as Qdrant implements it: each list's scores
           are normalised to [0, 1] against mean +/- 3 standard deviations, then summed.
"""

import statistics
from typing import Dict, Hashable, List, Optional, Sequence, Tuple


def rrf_fuse(rankings: Sequence[Sequence[Hashable]], k: int = 60,
             weights: Optional[Sequence[float]] = None) -> List[Tuple[Hashable, float]]:
    """
    Fuse ranked lists of keys. Returns (key, score), best first.

    Ties break on first appearance across the lists in order, so the result is
    deterministic -- a fused ranking that reshuffles between identical runs would make
    every metric computed from it noisy for no reason.
    """
    weights = list(weights) if weights is not None else [1.0] * len(rankings)
    scores: Dict[Hashable, float] = {}
    first_seen: Dict[Hashable, int] = {}
    order = 0
    for ranking, weight in zip(rankings, weights):
        for rank, key in enumerate(ranking, start=1):
            scores[key] = scores.get(key, 0.0) + weight / (k + rank)
            if key not in first_seen:
                first_seen[key] = order
                order += 1
    return sorted(scores.items(), key=lambda item: (-item[1], first_seen[item[0]]))


def _dbsf_normalise(scored: Sequence[Tuple[Hashable, float]]) -> Dict[Hashable, float]:
    values = [score for _, score in scored]
    if not values:
        return {}
    mean = statistics.fmean(values)
    spread = statistics.pstdev(values) if len(values) > 1 else 0.0
    low, high = mean - 3 * spread, mean + 3 * spread
    if high <= low:
        # One result, or all equal: nothing to distinguish them by, so all score the same.
        return {key: 0.5 for key, _ in scored}
    return {key: min(1.0, max(0.0, (score - low) / (high - low))) for key, score in scored}


def dbsf_fuse(result_lists: Sequence[Sequence[Tuple[Hashable, float]]]
              ) -> List[Tuple[Hashable, float]]:
    """Fuse (key, raw score) lists by distribution-normalised score sum, best first."""
    scores: Dict[Hashable, float] = {}
    first_seen: Dict[Hashable, int] = {}
    order = 0
    for scored in result_lists:
        for key, value in _dbsf_normalise(scored).items():
            scores[key] = scores.get(key, 0.0) + value
            if key not in first_seen:
                first_seen[key] = order
                order += 1
    return sorted(scores.items(), key=lambda item: (-item[1], first_seen[item[0]]))
