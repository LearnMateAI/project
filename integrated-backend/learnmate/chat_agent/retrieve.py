"""
Node 2 of 5: retrieve.

Searches the vector store, reranks what it found, and from the result decides which of the
two modes this turn runs in:

    pdf mode      the best chunk scored at or above the threshold. The reply will be
                  written from those chunks and judged strictly against them.
    general mode  nothing relevant came back. The reply will come from the model's own
                  knowledge and be judged only on relevance, coherence, informativeness.

Two stages, because they are good at different things. The vector search is the only thing
that can look at a whole corpus, and it compares the question and the chunk as two points
embedded independently -- fast, and blunt at the top of the list. The cross-encoder reads
each question/chunk pair together and scores it properly, which it can only afford to do
on a shortlist. So retrieval casts wide (RERANK_CANDIDATES) and the reranker narrows
(TOP_K). See llm/rerank.py.

The mode is decided by a score, not by asking a model whether it thinks the context is
useful. A number that can be tuned and logged beats a second LLM call that can be wrong --
and it costs nothing.

    standalone_query  -->  contexts, scores, mode, top_score
"""

import time
from typing import Dict, List, Tuple

from langchain_core.documents import Document

from .. import config
from ..llm import rerank as reranker
from ..runtime_limits import add_timing
from ..storage import bm25_store
from ..storage.vectors import get_vector_store
from .helpers import _log
from .state import ChatState


def _chunk_key(doc: Document) -> str:
    """Stable identity shared by ANN and BM25 — not the Qdrant UUID."""
    meta = doc.metadata or {}
    return bm25_store.chunk_key(meta.get("page_number"), meta.get("chunk_index"))


def _merge_hybrid(ann_hits: List[Tuple[Document, float]],
                  bm25_docs: List[Document], query: str, index
                  ) -> Tuple[List[Document], dict]:
    """
    Top 15 ANN + top 10 BM25, deduped by chunk_id. A chunk in both lists is kept once
    and tagged `both` — that is the signal later eval uses to see whether BM25 helped.
    """
    ann_keep = ann_hits[: config.BM25_ANN_KEEP]
    bm25_ranked = index.ranked(query, config.BM25_TOP_K)

    by_key = {}
    sources = {}
    ann_scores = {}
    for doc, score in ann_keep:
        key = _chunk_key(doc)
        by_key[key] = doc
        sources[key] = "ann"
        ann_scores[key] = float(score)
    for idx, _score in bm25_ranked:
        doc = bm25_docs[idx]
        key = _chunk_key(doc)
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

    scored = [(doc, ann_scores.get(_chunk_key(doc), 0.0)) for doc in merged]

    mix = {
        "ann": sum(1 for s in sources.values() if s == "ann"),
        "bm25": sum(1 for s in sources.values() if s == "bm25"),
        "both": sum(1 for s in sources.values() if s == "both"),
        "merged": len(merged),
    }
    return scored, mix


def _search(query: str, doc_id) -> Tuple[List, List[float], float, str, dict]:
    """
    Find the chunks for this question, as (contexts, scores, top_score, basis).

    `basis` names which threshold the caller should judge `top_score` against -- the two
    scales are not interchangeable, so it travels with the number rather than being
    re-derived from config further down.
    """
    # Cast wide when a reranker is going to narrow it again; ask for exactly what the
    # prompt needs when nothing will.
    use_reranker = reranker.available()
    k = max(config.RERANK_CANDIDATES, config.TOP_K) if use_reranker else config.TOP_K

    hits = get_vector_store().similarity_search_with_score(
        query,
        k=k,
        doc_id=doc_id,      # None searches every ingested document
    )
    mix = None
    if config.HYBRID_BM25 and doc_id is not None:
        index, bm25_docs = bm25_store.get_okapi(doc_id)
        if index is not None and bm25_docs:
            hits, mix = _merge_hybrid(hits or [], bm25_docs, query, index)
        # No sidecar and nothing to backfill: keep ANN-only rather than failing the turn.

    if not hits:
        return [], [], 0.0, "rerank" if use_reranker else "cosine", mix

    if use_reranker:
        ranked = reranker.rerank(query, [doc for doc, _ in hits], top_k=config.TOP_K)
        # None means the reranker did not run after all -- it failed to load between the
        # availability check and here, or a batch errored. Fall through to the vector
        # scores rather than losing the turn.
        if ranked is not None:
            # Drop the weak chunks rather than filling TOP_K regardless. Cosine scores are
            # too poorly separated to threshold one chunk at a time -- which is why the
            # pre-rerank code only ever tested the top one -- but a cross-encoder's are
            # not: on a typical question the chunk that answers it scores ~0.95 and a
            # contents-page fragment scores ~0.003. Passing that second one to the
            # generator is noise it has to read past, and prefill paid twice, once here
            # and again when the judge reads the same context block.
            #
            # The best chunk is always kept, even when it is weak: `top_score` is what
            # decides pdf-vs-general mode downstream, and that decision needs a number.
            keep = [pair for pair in ranked if pair[1] >= config.RERANK_THRESHOLD]
            keep = keep or ranked[:1]
            return ([doc for doc, _ in keep], [score for _, score in keep],
                    ranked[0][1], "rerank", mix)

    # Hits come back best-first. Both vector backends return raw cosine similarity, so
    # RELEVANCE_THRESHOLD means the same thing whichever one is configured.
    hits = hits[:config.TOP_K]
    return ([doc for doc, _ in hits], [score for _, score in hits], hits[0][1], "cosine",
            mix)


def retrieve_node(state: ChatState) -> Dict:
    """Retrieve context, rerank it, and decide the mode from the best score."""
    started = time.perf_counter()
    # Fall back to the raw query if rewrite produced nothing -- see rewrite.py, which
    # returns the original query on failure.
    query = state.get("standalone_query") or state["query"]

    contexts, scores, top_score, basis, mix = _search(query, state.get("doc_id"))

    threshold = (config.RERANK_THRESHOLD if basis == "rerank"
                 else config.RELEVANCE_THRESHOLD)
    grounded = bool(contexts) and top_score >= threshold

    extra = {"retrieval_mix": mix}

    if mix:
        kept = {}
        for doc in contexts:
            src = (doc.metadata or {}).get("retrieval_source") or "ann"
            kept[src] = kept.get(src, 0) + 1
        mix = {**mix, "rerank_kept": kept}
        extra["retrieval_mix"] = mix
        _log(state, f"[*] Retrieval mix ANN={mix['ann']} BM25={mix['bm25']} "
                    f"both={mix['both']}; reranker kept {kept}")

    extra["timings"] = add_timing(state, "retrieve_ms", started)

    if grounded:
        _log(state, f"[*] PDF mode ({basis} score {top_score:.4f} "
                    f">= {threshold:.2f}, {len(contexts)} chunks)")
        return {"contexts": contexts, "scores": scores,
                "mode": "pdf", "top_score": top_score, **extra}

    # Deliberately clear the contexts. Downstream nodes switch on "are there contexts",
    # so leaving weak chunks in place would ground the answer on irrelevant text and
    # then let the judge punish it for not matching.
    _log(state, f"[*] General mode ({basis} score {top_score:.4f} < {threshold:.2f})")
    return {"contexts": [], "scores": [], "mode": "general", "top_score": top_score,
            **extra}
