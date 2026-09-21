"""
Metric functions, pure and dependency-light, so tests can check them by hand.

Retrieval metrics take a ranked list of keys and the relevance of each key:

    recall_at_k   was a relevant item in the top k (binary: the gold chunk)
    mrr_at_k      1 / rank of the first relevant item within k, else 0
    ndcg_at_k     graded: gold chunk = 2, another chunk of the gold page = 1 (Jarvelin &
                  Kekalainen 2002, exponential gain)

paired_bootstrap compares two systems on the same queries -- the right test when every
query is answered by both, and it makes no normality assumption about per-query scores.
"""

import math
import random
from typing import Dict, Hashable, List, Optional, Sequence, Tuple


def recall_at_k(ranked: Sequence[Hashable], relevant: Sequence[Hashable], k: int) -> float:
    wanted = set(relevant)
    return 1.0 if any(key in wanted for key in ranked[:k]) else 0.0


def mrr_at_k(ranked: Sequence[Hashable], relevant: Sequence[Hashable], k: int) -> float:
    wanted = set(relevant)
    for rank, key in enumerate(ranked[:k], start=1):
        if key in wanted:
            return 1.0 / rank
    return 0.0


def ndcg_at_k(ranked: Sequence[Hashable], grades: Dict[Hashable, int], k: int) -> float:
    def dcg(gains: Sequence[int]) -> float:
        return sum((2 ** gain - 1) / math.log2(position + 2)
                   for position, gain in enumerate(gains))

    actual = dcg([grades.get(key, 0) for key in ranked[:k]])
    ideal = dcg(sorted(grades.values(), reverse=True)[:k])
    return actual / ideal if ideal > 0 else 0.0


def mean(values: Sequence[float]) -> Optional[float]:
    values = [v for v in values if v is not None]
    return sum(values) / len(values) if values else None


def percentile(values: Sequence[float], q: float) -> Optional[float]:
    """Linear-interpolated percentile, q in [0, 100]."""
    data = sorted(v for v in values if v is not None)
    if not data:
        return None
    if len(data) == 1:
        return data[0]
    position = (len(data) - 1) * q / 100.0
    low = math.floor(position)
    high = math.ceil(position)
    return data[low] + (data[high] - data[low]) * (position - low)


def latency_summary(values: Sequence[float]) -> Dict[str, Optional[float]]:
    return {"n": len(values), "mean": mean(values), "p50": percentile(values, 50),
            "p95": percentile(values, 95), "p99": percentile(values, 99)}


def prf1(tp: int, fp: int, fn: int) -> Dict[str, float]:
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"precision": precision, "recall": recall, "f1": f1}


def bootstrap_ci(values: Sequence[float], n: int = 1000, alpha: float = 0.05,
                 seed: int = 13) -> Tuple[float, float]:
    rng = random.Random(seed)
    values = list(values)
    if not values:
        return (float("nan"), float("nan"))
    means = sorted(sum(rng.choice(values) for _ in values) / len(values) for _ in range(n))
    return means[int(n * alpha / 2)], means[int(n * (1 - alpha / 2)) - 1]


def paired_bootstrap(a: Sequence[float], b: Sequence[float], n: int = 1000,
                     seed: int = 13) -> Dict[str, float]:
    """
    Is system b better than system a on these queries? Resamples query indices.

    Returns the observed mean difference (b - a) and the one-sided p-value: the share of
    resamples in which b did not beat a.
    """
    assert len(a) == len(b), "paired comparison needs the same queries"
    rng = random.Random(seed)
    diffs = [y - x for x, y in zip(a, b)]
    observed = sum(diffs) / len(diffs) if diffs else 0.0
    if not diffs:
        return {"delta": 0.0, "p_value": 1.0}
    not_better = 0
    for _ in range(n):
        sample = [rng.choice(diffs) for _ in diffs]
        if sum(sample) / len(sample) <= 0:
            not_better += 1
    return {"delta": observed, "p_value": not_better / n}


def nmi_ari(truth: Sequence[Hashable], labels: Sequence[int],
            noise_as_singletons: bool = False) -> Dict[str, float]:
    """NMI and ARI of a clustering against gold labels (sklearn)."""
    from sklearn.metrics import adjusted_rand_score, normalized_mutual_info_score

    pairs = list(zip(truth, labels))
    if noise_as_singletons:
        pairs = [(t, label if label != -1 else f"noise-{i}") for i, (t, label) in enumerate(pairs)]
    else:
        pairs = [(t, label) for t, label in pairs if label != -1]
    if len(pairs) < 2:
        return {"nmi": float("nan"), "ari": float("nan"), "n": len(pairs)}
    gold = [str(t) for t, _ in pairs]
    pred = [str(label) for _, label in pairs]
    return {"nmi": normalized_mutual_info_score(gold, pred),
            "ari": adjusted_rand_score(gold, pred), "n": len(pairs)}
