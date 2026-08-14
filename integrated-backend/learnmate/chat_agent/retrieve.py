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

from typing import Dict, List, Tuple

from .. import config
from ..llm import rerank as reranker
from ..storage.vectors import get_vector_store
from .helpers import _log
from .state import ChatState


def _search(query: str, doc_id) -> Tuple[List, List[float], float, str]:
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
    if not hits:
        return [], [], 0.0, "rerank" if use_reranker else "cosine"

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
                    ranked[0][1], "rerank")

    # Hits come back best-first. Both vector backends return raw cosine similarity, so
    # RELEVANCE_THRESHOLD means the same thing whichever one is configured.
    hits = hits[:config.TOP_K]
    return ([doc for doc, _ in hits], [score for _, score in hits], hits[0][1], "cosine")


def retrieve_node(state: ChatState) -> Dict:
    """Retrieve context, rerank it, and decide the mode from the best score."""
    # Fall back to the raw query if rewrite produced nothing -- see rewrite.py, which
    # returns the original query on failure.
    query = state.get("standalone_query") or state["query"]

    contexts, scores, top_score, basis = _search(query, state.get("doc_id"))

    threshold = (config.RERANK_THRESHOLD if basis == "rerank"
                 else config.RELEVANCE_THRESHOLD)
    grounded = bool(contexts) and top_score >= threshold

    if grounded:
        _log(state, f"[*] PDF mode ({basis} score {top_score:.4f} "
                    f">= {threshold:.2f}, {len(contexts)} chunks)")
        return {"contexts": contexts, "scores": scores,
                "mode": "pdf", "top_score": top_score}

    # Deliberately clear the contexts. Downstream nodes switch on "are there contexts",
    # so leaving weak chunks in place would ground the answer on irrelevant text and
    # then let the judge punish it for not matching.
    _log(state, f"[*] General mode ({basis} score {top_score:.4f} < {threshold:.2f})")
    return {"contexts": [], "scores": [], "mode": "general", "top_score": top_score}
