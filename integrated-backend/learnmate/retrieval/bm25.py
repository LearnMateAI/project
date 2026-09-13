"""
Okapi BM25 over one document's chunks.

No extra package: a few dozen lines, enough for hybrid retrieve. Built at ingest and
scored at query time against the rewritten question, never the raw user message.
"""

from __future__ import annotations

import math
import re
from typing import Iterable, List, Sequence, Tuple

_TOKEN = re.compile(r"[a-z0-9]+", re.IGNORECASE)


def tokenize(text: str) -> List[str]:
    return _TOKEN.findall((text or "").lower())


class BM25Okapi:
    """Standard BM25 (k1=1.5, b=0.75) over a pre-tokenised corpus."""

    def __init__(self, corpus: Sequence[Sequence[str]], k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.corpus = [list(doc) for doc in corpus]
        self.n = len(self.corpus)
        self.doc_len = [len(doc) or 1 for doc in self.corpus]
        self.avgdl = (sum(self.doc_len) / self.n) if self.n else 1.0
        df = {}
        for doc in self.corpus:
            for term in set(doc):
                df[term] = df.get(term, 0) + 1
        self.idf = {
            term: math.log(1.0 + (self.n - freq + 0.5) / (freq + 0.5))
            for term, freq in df.items()
        }

    def score(self, query: Iterable[str], index: int) -> float:
        doc = self.corpus[index]
        if not doc:
            return 0.0
        tf = {}
        for term in doc:
            tf[term] = tf.get(term, 0) + 1
        length = self.doc_len[index]
        total = 0.0
        for term in query:
            if term not in tf:
                continue
            freq = tf[term]
            idf = self.idf.get(term, 0.0)
            denom = freq + self.k1 * (1 - self.b + self.b * length / self.avgdl)
            total += idf * (freq * (self.k1 + 1) / denom)
        return total

    def ranked(self, query_text: str, top_k: int) -> List[Tuple[int, float]]:
        query = tokenize(query_text)
        if not query or not self.corpus:
            return []
        scored = [(i, self.score(query, i)) for i in range(self.n)]
        scored.sort(key=lambda pair: pair[1], reverse=True)
        return [(i, s) for i, s in scored[:top_k] if s > 0]
