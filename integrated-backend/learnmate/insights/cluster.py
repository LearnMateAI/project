"""
Grouping questions into topics: embed, cluster, label.

    questions --MiniLM--> unit vectors --HDBSCAN--> clusters (+ noise) --c-TF-IDF--> labels

The recipe is BERTopic's (Grootendorst, 2022) without its dependency tree: sentence
embeddings, density-based clustering, and class-based TF-IDF for the labels. UMAP, which
BERTopic puts in front of HDBSCAN, is left out -- at a few hundred to a few thousand short
questions per document, HDBSCAN on the 384-d vectors directly is fast and stable, and one
fewer stochastic stage makes the result reproducible.

Why HDBSCAN rather than k-means: nobody knows how many topics a class will ask about, and
not every question belongs to one. HDBSCAN finds the number itself and labels stragglers
as noise instead of forcing them into the nearest topic -- a one-off question is not a
point of confusion.

Vectors are L2-normalised, so Euclidean distance is a monotone function of cosine
(|a-b|^2 = 2 - 2cos) and the density estimate works in the space the embedder was trained
for.
"""

import math
from collections import Counter
from typing import Dict, List, Sequence

import numpy as np

from ..retrieval.analyzer import display_tokens

# Words that make a sentence a question rather than say what it is about. They would top
# every cluster's c-TF-IDF otherwise -- "explain" is in half of all questions.
QUESTION_WORDS = frozenset("""
explain describe define definition meaning mean means tell give example examples discuss
list difference differences compare between briefly please main key role purpose
importance important use used uses work works happen happens according document text
page section chapter question answer
""".split())


def embed(texts: Sequence[str]) -> np.ndarray:
    from ..llm.embeddings import get_embeddings

    vectors = np.asarray(get_embeddings().embed_documents(list(texts)), dtype=np.float32)
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    return vectors / np.clip(norms, 1e-12, None)


def cluster(vectors: np.ndarray, min_cluster_size: int, min_samples: int) -> np.ndarray:
    """HDBSCAN labels; -1 is noise. Everything is noise below min_cluster_size points."""
    n = len(vectors)
    if n < max(2, min_cluster_size):
        return np.full(n, -1, dtype=int)
    from sklearn.cluster import HDBSCAN

    model = HDBSCAN(min_cluster_size=min_cluster_size,
                    min_samples=min(min_samples, n - 1) if min_samples else None,
                    metric="euclidean", copy=True)
    return model.fit_predict(vectors).astype(int)


def _terms(text: str) -> List[str]:
    return [token for token in display_tokens(text)
            if token not in QUESTION_WORDS and not token.isdigit() and len(token) > 2]


def ctfidf(docs_by_cluster: Dict[int, List[str]], top_n: int = 5) -> Dict[int, List[str]]:
    """
    Top terms per cluster by class-based TF-IDF.

        W(t, c) = tf(t, c) * log(1 + A / f(t))

    tf(t, c) is t's frequency within cluster c, normalised by the cluster's term count;
    f(t) is t's frequency across all clusters; A is the average term count per cluster.
    A term frequent in one cluster and rare elsewhere wins; a term frequent everywhere is
    discounted however often it appears.
    """
    counts = {c: Counter(term for doc in docs for term in _terms(doc))
              for c, docs in docs_by_cluster.items()}
    counts = {c: counter for c, counter in counts.items() if counter}
    if not counts:
        return {c: [] for c in docs_by_cluster}
    totals = Counter()
    for counter in counts.values():
        totals.update(counter)
    average = sum(sum(counter.values()) for counter in counts.values()) / len(counts)

    labels = {}
    for c, counter in counts.items():
        size = sum(counter.values())
        weights = {term: (tf / size) * math.log(1.0 + average / totals[term])
                   for term, tf in counter.items()}
        labels[c] = [term for term, _ in sorted(weights.items(),
                                                key=lambda item: (-item[1], item[0]))[:top_n]]
    for c in docs_by_cluster:
        labels.setdefault(c, [])
    return labels
