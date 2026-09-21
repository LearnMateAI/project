"""
One retriever, several strategies, and the pdf/general decision.

    search(query, doc_id, k, strategy)   ->  RetrievalResult   candidates, best first
    decide(query, result, use_reranker)  ->  Decision          what reaches the prompt

Everything that retrieves goes through here -- the chat agent's retrieve node, the page
picker behind topic-scoped study resources, and the evaluation harness -- so an ablation
measures the code path a student actually hits rather than a re-implementation of it.

Strategies (config.RETRIEVAL_STRATEGY):

    legacy       dense ANN top-15 unioned with an in-process BM25 top-10, unfused. What
                 this system ran before, kept verbatim as the baseline.
    dense        dense ANN only.
    bm25         Qdrant's sparse index only: stemmed BM25, IDF computed by the server.
    rrf          dense + bm25 fused by reciprocal rank inside one Qdrant query.
    dbsf         dense + bm25 fused by distribution-normalised score.
    splade       learned sparse only (ablation).
    rrf_splade   dense + learned sparse, RRF (ablation).

The Qdrant strategies need a v2 collection (scripts/reindex_qdrant.py). On the MongoDB
vector backend, `dense`, `bm25`, `rrf` and `dbsf` are fused here in Python over the
in-process BM25 index instead. A strategy the store cannot serve falls back to `legacy`,
warns once, and records what actually ran -- a retrieval choice must never fail a turn.

The decision is the one retrieve.py always made: the cross-encoder's best score against
RERANK_THRESHOLD when reranking runs, otherwise cosine against RELEVANCE_THRESHOLD. What
is new is that the fallback always compares a real cosine. A fused score is a rank, not a
similarity (the top hit scores high however poor the match), so the fused strategies
fetch each candidate's dense vector and threshold its cosine instead.
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

from langchain_core.documents import Document

from .. import config
from ..llm import rerank as reranker
from ..storage import bm25_store
from ..storage.vectors import get_vector_store
from .fusion import dbsf_fuse, rrf_fuse

logger = logging.getLogger("learnmate.retrieval")

LEGACY = "legacy"
STRATEGIES = ("legacy", "dense", "bm25", "rrf", "dbsf", "splade", "rrf_splade")

# Strategies warned about once already, so a misconfigured server logs one line rather
# than one per question.
_WARNED = set()


@dataclass
class Hit:
    """One candidate chunk."""
    doc: Document
    score: float                       # the strategy's own ranking score
    dense_cos: Optional[float] = None  # query-chunk cosine, whatever the ranking was
    source: str = ""                   # ann / bm25 / both / fused / dense / sparse


@dataclass
class RetrievalResult:
    hits: List[Hit]
    strategy: str                      # what actually ran
    requested: str                     # what was asked for
    mix: Optional[Dict] = None         # legacy only: how many came from ANN / BM25 / both
    timings: Dict[str, int] = field(default_factory=dict)


@dataclass
class Decision:
    contexts: List[Document]           # what reaches the prompt in pdf mode
    scores: List[float]                # aligned with contexts, on the `basis` scale
    top_score: float                   # the number the mode was decided on
    basis: str                         # "rerank" or "cosine"
    mode: str                          # "pdf" or "general"
    threshold: float
    # The best candidate whether or not it was good enough. Kept in general mode too,
    # where contexts are cleared: "which part of the document was this question nearest
    # to" is what the confusion heatmap attributes an unanswerable question with.
    nearest: Optional[Dict] = None
    rerank_ms: int = 0


def chunk_key(doc: Document) -> str:
    """Stable identity shared by every strategy -- (page, chunk), never a point id."""
    meta = doc.metadata or {}
    return bm25_store.chunk_key(meta.get("page_number"), meta.get("chunk_index"))


def candidate_k(use_reranker: bool) -> int:
    """Cast wide when a reranker will narrow it again; exactly TOP_K when nothing will."""
    return max(config.RERANK_CANDIDATES, config.TOP_K) if use_reranker else config.TOP_K


# --- legacy: moved here verbatim from chat_agent/retrieve.py ------------------------------

def _merge_hybrid(ann_hits: List[Tuple[Document, float]],
                  bm25_docs: List[Document], query: str, index
                  ) -> Tuple[List[Tuple[Document, float]], dict]:
    """
    Top 15 ANN + top 10 BM25, deduped by chunk_id. A chunk in both lists is kept once
    and tagged `both` -- that is the signal later eval uses to see whether BM25 helped.
    """
    ann_keep = ann_hits[: config.BM25_ANN_KEEP]
    bm25_ranked = index.ranked(query, config.BM25_TOP_K)

    by_key = {}
    sources = {}
    ann_scores = {}
    for doc, score in ann_keep:
        key = chunk_key(doc)
        by_key[key] = doc
        sources[key] = "ann"
        ann_scores[key] = float(score)
    for idx, _score in bm25_ranked:
        doc = bm25_docs[idx]
        key = chunk_key(doc)
        if key in sources:
            sources[key] = "both"
        else:
            by_key[key] = doc
            sources[key] = "bm25"

    merged = []
    for key, doc in by_key.items():
        meta = dict(doc.metadata or {})
        meta["retrieval_source"] = sources[key]
        merged.append(Document(page_content=doc.page_content, metadata=meta))

    scored = [(doc, ann_scores.get(chunk_key(doc), 0.0)) for doc in merged]

    mix = {
        "ann": sum(1 for s in sources.values() if s == "ann"),
        "bm25": sum(1 for s in sources.values() if s == "bm25"),
        "both": sum(1 for s in sources.values() if s == "both"),
        "merged": len(merged),
    }
    return scored, mix


def _legacy(query: str, doc_id, k: int) -> Tuple[List[Hit], Optional[dict]]:
    hits = get_vector_store().similarity_search_with_score(query, k=k, doc_id=doc_id)
    mix = None
    if config.HYBRID_BM25 and doc_id is not None:
        index, bm25_docs = bm25_store.get_okapi(doc_id)
        if index is not None and bm25_docs:
            hits, mix = _merge_hybrid(hits or [], bm25_docs, query, index)
        # No sidecar and nothing to backfill: keep ANN-only rather than failing the turn.
    return [Hit(doc=doc, score=float(score),
                source=(doc.metadata or {}).get("retrieval_source") or "ann")
            for doc, score in hits or []], mix


# --- app-side strategies, for stores that cannot fuse (MongoDB) ---------------------------

def _app_side(strategy: str, query: str, doc_id, k: int,
              query_vector: Optional[List[float]]) -> List[Hit]:
    store = get_vector_store()
    wide = max(k, config.HYBRID_PREFETCH)
    dense_hits = store.similarity_search_with_score(query, k=wide, doc_id=doc_id) \
        if strategy in ("dense", "rrf", "dbsf") else []
    cosine = {chunk_key(doc): float(score) for doc, score in dense_hits}
    if strategy == "dense":
        return [Hit(doc=doc, score=float(score), dense_cos=float(score), source="dense")
                for doc, score in dense_hits[:k]]

    index, bm25_docs = bm25_store.get_okapi(doc_id)
    lexical = [(bm25_docs[i], float(s)) for i, s in index.ranked(query, wide)] \
        if index is not None else []
    by_key = {chunk_key(doc): doc for doc, _ in dense_hits + lexical}

    if strategy == "bm25":
        fused = [(chunk_key(doc), score) for doc, score in lexical]
    elif strategy == "rrf":
        fused = rrf_fuse([[chunk_key(d) for d, _ in dense_hits],
                          [chunk_key(d) for d, _ in lexical]], k=config.RRF_K or 60)
    else:
        fused = dbsf_fuse([[(chunk_key(d), s) for d, s in dense_hits],
                           [(chunk_key(d), s) for d, s in lexical]])
    return [Hit(doc=by_key[key], score=float(score), dense_cos=cosine.get(key),
                source="fused" if strategy != "bm25" else "sparse")
            for key, score in fused[:k]]


# --- the entry points -----------------------------------------------------------------

def _warn_once(strategy: str, reason: str) -> None:
    if strategy not in _WARNED:
        _WARNED.add(strategy)
        logger.warning("Retrieval strategy %r unavailable (%s); using legacy.",
                       strategy, reason)


def search(query: str, doc_id, k: int, strategy: Optional[str] = None,
           query_vector: Optional[List[float]] = None) -> RetrievalResult:
    """Up to `k` candidate chunks for `query` within one document, best first."""
    requested = (strategy or config.RETRIEVAL_STRATEGY).lower()
    timings: Dict[str, int] = {}
    started = time.perf_counter()

    if requested not in STRATEGIES:
        _warn_once(requested, "unknown strategy")
        requested_run = LEGACY
    else:
        requested_run = requested

    if requested_run != LEGACY:
        store = get_vector_store()
        try:
            if hasattr(store, "query"):
                if not store.supports(requested_run):
                    raise ValueError(f"collection is {getattr(store, 'schema', '?')}")
                if query_vector is None:
                    embed_started = time.perf_counter()
                    query_vector = store.embeddings.embed_query(query)
                    timings["embed_ms"] = int((time.perf_counter() - embed_started) * 1000)
                search_started = time.perf_counter()
                rows = store.query(requested_run, query, query_vector, k, doc_id=doc_id)
                timings["search_ms"] = int((time.perf_counter() - search_started) * 1000)
                source = {"dense": "dense", "bm25": "sparse",
                          "splade": "sparse"}.get(requested_run, "fused")
                hits = [Hit(doc=doc, score=score, dense_cos=cos, source=source)
                        for doc, score, cos in rows]
            elif requested_run in ("dense", "bm25", "rrf", "dbsf") and doc_id is not None:
                hits = _app_side(requested_run, query, doc_id, k, query_vector)
            else:
                raise ValueError("the configured vector store cannot fuse")
            timings["retrieve_total_ms"] = int((time.perf_counter() - started) * 1000)
            return RetrievalResult(hits=hits, strategy=requested_run, requested=requested,
                                   timings=timings)
        except Exception as exc:
            # A bad strategy must degrade retrieval, never lose the answer.
            _warn_once(requested_run, f"{type(exc).__name__}: {exc}")

    hits, mix = _legacy(query, doc_id, k)
    timings["retrieve_total_ms"] = int((time.perf_counter() - started) * 1000)
    return RetrievalResult(hits=hits, strategy=LEGACY, requested=requested, mix=mix,
                           timings=timings)


def _nearest(doc: Document, score: float) -> Dict:
    meta = doc.metadata or {}
    return {"page": meta.get("page_number"), "chunk_index": meta.get("chunk_index"),
            "score": round(float(score), 4)}


def decide(query: str, result: RetrievalResult, use_reranker: bool,
           top_k: Optional[int] = None) -> Decision:
    """
    Narrow the candidates to what reaches the prompt, and pick the mode.

    Identical to what chat_agent/retrieve.py did before this module existed, for every
    strategy: rerank to TOP_K, drop chunks under RERANK_THRESHOLD but always keep the best,
    and decide pdf-vs-general on the best score. Without a reranker, the first TOP_K by
    the strategy's own order, thresholded on cosine.
    """
    top_k = top_k or config.TOP_K
    hits = result.hits
    if not hits:
        basis = "rerank" if use_reranker else "cosine"
        threshold = config.RERANK_THRESHOLD if use_reranker else config.RELEVANCE_THRESHOLD
        return Decision([], [], 0.0, basis, "general", threshold)

    if use_reranker:
        started = time.perf_counter()
        ranked = reranker.rerank(query, [hit.doc for hit in hits], top_k=top_k)
        rerank_ms = int((time.perf_counter() - started) * 1000)
        # None means the reranker did not run after all -- it failed to load between the
        # availability check and here, or a batch errored. Fall through to the vector
        # scores rather than losing the turn.
        if ranked is not None:
            # Drop the weak chunks rather than filling TOP_K regardless: a cross-encoder
            # separates "answers it" (~0.95) from "a contents-page fragment" (~0.003) well
            # enough to threshold one chunk at a time, which cosine never could. The best
            # chunk is always kept -- the mode decision needs a number.
            keep = [pair for pair in ranked if pair[1] >= config.RERANK_THRESHOLD]
            keep = keep or ranked[:1]
            top = float(ranked[0][1])
            threshold = config.RERANK_THRESHOLD
            return Decision(
                contexts=[doc for doc, _ in keep], scores=[score for _, score in keep],
                top_score=top, basis="rerank",
                mode="pdf" if top >= threshold else "general", threshold=threshold,
                nearest=_nearest(ranked[0][0], top), rerank_ms=rerank_ms)

    kept = hits[:top_k]
    scores = [hit.dense_cos if hit.dense_cos is not None else hit.score for hit in kept]
    best = max(range(len(kept)), key=lambda i: scores[i])
    top = float(scores[best])
    threshold = config.RELEVANCE_THRESHOLD
    return Decision(contexts=[hit.doc for hit in kept], scores=scores, top_score=top,
                    basis="cosine", mode="pdf" if top >= threshold else "general",
                    threshold=threshold, nearest=_nearest(kept[best].doc, top))


def summary(result: RetrievalResult, decision: Decision) -> Dict:
    """The compact record of how a turn retrieved, stored on the assistant turn."""
    nearest = decision.nearest or {}
    return {
        "strategy": result.strategy,
        "requested": result.requested,
        "basis": decision.basis,
        "top_score": round(float(decision.top_score), 4),
        "top_page": nearest.get("page"),
        "top_chunk": nearest.get("chunk_index"),
        "candidates": len(result.hits),
    }


def rank_pages(query: str, doc_id, k: int, strategy: Optional[str] = None,
               rerank: bool = False) -> List[int]:
    """
    Page numbers ordered by their best chunk's rank, for topic-scoped resources.

    `legacy` is the page picker's original plain vector search, not the chat baseline:
    the union with BM25 is unranked, and ordering pages by it would change which pages a
    topic resource is written from.
    """
    strategy = (strategy or config.TOPIC_RETRIEVAL_STRATEGY).lower()
    if strategy == LEGACY:
        docs = [doc for doc, _ in
                get_vector_store().similarity_search_with_score(query, k=k, doc_id=doc_id)]
    else:
        result = search(query, doc_id, k, strategy=strategy)
        docs = [hit.doc for hit in result.hits]
        if rerank and docs:
            ranked = reranker.rerank(query, docs, top_k=len(docs))
            if ranked is not None:
                docs = [doc for doc, _ in ranked]

    pages, seen = [], set()
    for doc in docs:
        number = (doc.metadata or {}).get("page_number")
        # De-duplicated: several chunks of one page can all rank highly, and the page is
        # read whole either way.
        if number is not None and number not in seen:
            seen.add(number)
            pages.append(number)
    return pages


def page_keys(docs: Sequence[Document]) -> List[str]:
    """chunk_key for each document, for metric code that compares against gold labels."""
    return [chunk_key(doc) for doc in docs]
