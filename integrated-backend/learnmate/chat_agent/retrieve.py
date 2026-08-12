"""
Node 2 of 5: retrieve.

Searches the vector store and, from the result, decides which of the two modes this turn
runs in:

    pdf mode      the top chunk scored at or above RELEVANCE_THRESHOLD. The reply will be
                  written from those chunks and judged strictly against them.
    general mode  nothing relevant came back. The reply will come from the model's own
                  knowledge and be judged only on relevance, coherence, informativeness.

The mode is decided by the retrieval score, not by asking the model whether it thinks the
context is useful. A number that can be tuned and logged beats a second LLM call that can
be wrong -- and it costs nothing.

    standalone_query  -->  contexts, scores, mode, top_score
"""

from typing import Dict

from .. import config
from ..storage.vectors import get_vector_store
from .helpers import _log
from .state import ChatState


def retrieve_node(state: ChatState) -> Dict:
    """Retrieve context and decide the mode from the top score."""
    # Fall back to the raw query if rewrite produced nothing -- see rewrite.py, which
    # returns the original query on failure.
    hits = get_vector_store().similarity_search_with_score(
        state.get("standalone_query") or state["query"],
        k=config.TOP_K,
        doc_id=state.get("doc_id"),      # None searches every ingested document
    )

    # Both vector backends return raw cosine similarity, so this threshold means the
    # same thing whichever one is configured. Hits come back best-first.
    top_score = hits[0][1] if hits else 0.0
    grounded = bool(hits) and top_score >= config.RELEVANCE_THRESHOLD

    if grounded:
        _log(state, f"[*] PDF mode (top retrieval score {top_score:.4f})")
        return {"contexts": [doc for doc, _ in hits],
                "scores": [score for _, score in hits],
                "mode": "pdf", "top_score": top_score}

    # Deliberately clear the contexts. Downstream nodes switch on "are there contexts",
    # so leaving weak chunks in place would ground the answer on irrelevant text and
    # then let the judge punish it for not matching.
    _log(state, f"[*] General mode (top retrieval score {top_score:.4f})")
    return {"contexts": [], "scores": [], "mode": "general", "top_score": top_score}
