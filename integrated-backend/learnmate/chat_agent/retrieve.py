"""
Node 2 of 5: retrieve.

Searches the document, reranks what it found, and from the result decides which of the two
modes this turn runs in:

    pdf mode      the best chunk scored at or above the threshold. The reply will be
                  written from those chunks and judged strictly against them.
    general mode  nothing relevant came back. The reply will come from the model's own
                  knowledge and be judged only on relevance, coherence, informativeness.

Two stages, because they are good at different things. First-stage retrieval is the only
thing that can look at a whole document -- dense vectors, BM25, or both fused inside Qdrant,
per LEARNMATE_RETRIEVAL_STRATEGY. The cross-encoder reads each question/chunk pair together
and scores it properly, which it can only afford to do on a shortlist. So retrieval casts
wide (RERANK_CANDIDATES) and the reranker narrows (TOP_K). The strategies, and the decision
rule both share, live in learnmate/retrieval/retriever.py.

The mode is decided by a score, not by asking a model whether it thinks the context is
useful. A number that can be tuned and logged beats a second LLM call that can be wrong --
and it costs nothing.

    standalone_query  -->  contexts, scores, mode, top_score, retrieval
"""

import time
from typing import Dict

from ..llm import rerank as reranker
from ..retrieval import retriever
from ..runtime_limits import add_timing
from .helpers import _log
from .state import ChatState


def retrieve_node(state: ChatState) -> Dict:
    """Retrieve context, rerank it, and decide the mode from the best score."""
    started = time.perf_counter()
    # Fall back to the raw query if rewrite produced nothing -- see rewrite.py, which
    # returns the original query on failure.
    query = state.get("standalone_query") or state["query"]

    use_reranker = reranker.available()
    result = retriever.search(query, state.get("doc_id"),
                              k=retriever.candidate_k(use_reranker),
                              # Embedded once per turn: the cache lookup, when it ran,
                              # already has this vector.
                              query_vector=state.get("query_vec"))
    decision = retriever.decide(query, result, use_reranker)

    mix = result.mix
    if mix:
        kept = {}
        for doc in decision.contexts:
            src = (doc.metadata or {}).get("retrieval_source") or "ann"
            kept[src] = kept.get(src, 0) + 1
        mix = {**mix, "rerank_kept": kept}
        _log(state, f"[*] Retrieval mix ANN={mix['ann']} BM25={mix['bm25']} "
                    f"both={mix['both']}; reranker kept {kept}")

    extra = {"retrieval_mix": mix,
             "retrieval": retriever.summary(result, decision),
             "timings": add_timing(state, "retrieve_ms", started)}

    if decision.mode == "pdf":
        _log(state, f"[*] PDF mode ({decision.basis} score {decision.top_score:.4f} "
                    f">= {decision.threshold:.2f}, {len(decision.contexts)} chunks, "
                    f"{result.strategy})")
        return {"contexts": decision.contexts, "scores": decision.scores,
                "mode": "pdf", "top_score": decision.top_score, **extra}

    # Deliberately clear the contexts. Downstream nodes switch on "are there contexts",
    # so leaving weak chunks in place would ground the answer on irrelevant text and
    # then let the judge punish it for not matching.
    _log(state, f"[*] General mode ({decision.basis} score {decision.top_score:.4f} "
                f"< {decision.threshold:.2f})")
    return {"contexts": [], "scores": [], "mode": "general",
            "top_score": decision.top_score, **extra}
