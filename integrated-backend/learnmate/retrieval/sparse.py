"""
Sparse vectors for Qdrant's server-side lexical index.

Okapi BM25 splits cleanly into a document half and a query half:

    score(q, d) = sum over t in q of   IDF(t)  *  tf(t,d) (k1 + 1) / (tf(t,d) + k1 (1 - b + b |d| / avgdl))
                                       ------     -------------------------------------------------------
                                       query       document: known at ingest, stored as the vector value

Qdrant's `Modifier.IDF` computes IDF(t) on the server from the collection's own statistics
at query time, so a document's vector holds only the saturated term frequency on the right,
and a query's vector is 1.0 per distinct term. Their dot product, with the modifier applied,
is BM25 -- computed where the postings live rather than by scanning every chunk of the
document in Python, which is what storage/bm25_store.py does.

The previous sparse vector (still written into legacy collections, see
storage/qdrant_vectors.py) was raw word counts with no IDF and no length normalisation: "the"
counted as much as "estoppel", and a long chunk outscored a short one for being long.

Term ids are a 31-bit hash of the analyzed token. Stable across processes and machines --
Python's own `hash()` is salted per process and would scramble the index on every restart
-- and wide enough that a textbook's vocabulary (tens of thousands of stems) collides
rarely. A collision merges two terms' weights; it costs precision on those two, nothing else.
"""

import hashlib
import threading
from collections import Counter
from typing import Dict, List, Optional, Sequence, Tuple

from .analyzer import ANALYZER_VERSION, analyze

__all__ = ["ANALYZER_VERSION", "term_id", "bm25_doc_vector", "bm25_query_vector",
           "mean_doc_length", "SparseEncoderWrapper"]

SparseVec = Tuple[List[int], List[float]]


def term_id(token: str) -> int:
    """A deterministic 31-bit id for one index term."""
    digest = hashlib.blake2b(token.encode("utf-8"), digest_size=4).digest()
    return int.from_bytes(digest, "little") & 0x7FFFFFFF


def _merge(pairs) -> SparseVec:
    """Collapse (id, weight) pairs into Qdrant's sorted, duplicate-free form."""
    merged: Dict[int, float] = {}
    for index, weight in pairs:
        merged[index] = merged.get(index, 0.0) + weight
    indices = sorted(merged)
    return indices, [float(merged[i]) for i in indices]


def bm25_doc_vector(text: str, k1: float, b: float, avgdl: float) -> SparseVec:
    """The document half of BM25: saturated, length-normalised term frequencies."""
    terms = analyze(text)
    if not terms:
        return [], []
    length = len(terms)
    avgdl = avgdl if avgdl and avgdl > 0 else float(length)
    norm = k1 * (1.0 - b + b * length / avgdl)
    counts = Counter(terms)
    return _merge((term_id(term), tf * (k1 + 1.0) / (tf + norm))
                  for term, tf in counts.items())


def bm25_query_vector(text: str) -> SparseVec:
    """
    The query half: 1.0 per distinct term, with IDF supplied by the server.

    Distinct rather than counted, as in Lucene and Qdrant's own bm25 model. A student
    asking "what is a trust and what is a trust deed" is not asking about trusts twice as
    much as a student who says it once.
    """
    return _merge((term_id(term), 1.0) for term in set(analyze(text)))


def mean_doc_length(texts: Sequence[str]) -> float:
    """avgdl over a set of chunks, in analyzed terms."""
    lengths = [len(analyze(text)) for text in texts]
    lengths = [n for n in lengths if n]
    return (sum(lengths) / len(lengths)) if lengths else 0.0


class SparseEncoderWrapper:
    """
    A learned sparse encoder (SPLADE family) through sentence-transformers' SparseEncoder.

    An ablation, not the default: it expands a query into related vocabulary the way
    BM25 cannot ("dismissal" also lights up "termination"), at the cost of a transformer
    forward pass per chunk at ingest and per query at search. Loaded lazily and guarded
    like the reranker, because the worker and the warm-up thread can both reach it.
    """

    _CACHE: Dict[str, object] = {}
    _LOAD_LOCK = threading.Lock()
    _PREDICT_LOCK = threading.Lock()

    def __init__(self, model_name: str):
        self.model_name = model_name

    def _model(self):
        if self.model_name not in self._CACHE:
            with self._LOAD_LOCK:
                if self.model_name not in self._CACHE:
                    from sentence_transformers import SparseEncoder

                    print(f"[*] Loading sparse encoder: {self.model_name} (first load only)...")
                    self._CACHE[self.model_name] = SparseEncoder(self.model_name)
        return self._CACHE[self.model_name]

    def _encode(self, texts: List[str], query: bool) -> List[SparseVec]:
        model = self._model()
        with self._PREDICT_LOCK:
            method = model.encode_query if query else model.encode_document
            tensors = method(texts, convert_to_tensor=True)
        out: List[SparseVec] = []
        for row in tensors:
            row = row.coalesce() if row.is_sparse else row.to_sparse().coalesce()
            indices = row.indices()[0].tolist()
            values = row.values().tolist()
            out.append(_merge(zip(indices, values)))
        return out

    def encode_documents(self, texts: List[str]) -> List[SparseVec]:
        return self._encode(list(texts), query=False) if texts else []

    def encode_query(self, text: str) -> SparseVec:
        return self._encode([text], query=True)[0]


_SPLADE: Optional[SparseEncoderWrapper] = None


def get_splade(model_name: str) -> SparseEncoderWrapper:
    global _SPLADE
    if _SPLADE is None or _SPLADE.model_name != model_name:
        _SPLADE = SparseEncoderWrapper(model_name)
    return _SPLADE
