"""
The answer cache's two nodes, wired in only when LEARNMATE_CACHE_ENABLED is on.

    rewrite -> cache_lookup -+-> (hit)  persist -> cache_store -> END
                             |
                             +-> (miss) retrieve -> generate -> evaluate -> ... -> persist -> cache_store -> END

The lookup runs after rewrite on purpose: a follow-up like "what about his powers?" is only
comparable with other students' questions once it has been resolved into a standalone one.
It embeds that question once and leaves the vector on the state, so a miss costs retrieval
nothing extra.

A hit goes straight to persist with the cached answer, its citations and the chunks it was
written from, so the turn is recorded -- and shown -- exactly like any other grounded
reply, plus a `cache` block saying it was reused and how close the match was.

Neither node may fail a turn. A cache that is down, slow to load its verifier, or pointed at
a missing collection degrades to "no cache", with the reason logged.
"""

import time
from typing import Dict

from langchain_core.documents import Document

from .. import config
from ..cache import get_answer_cache, should_store
from ..runtime_limits import JobTimeout, add_timing
from .helpers import _emit_reply, _emit_token, _log
from .state import ChatState


def cache_active(state: ChatState) -> bool:
    """On for this turn? The server flag, narrowed (never widened) by the request."""
    return (config.CACHE_ENABLED and state.get("use_cache") is not False
            and state.get("doc_id") is not None)


def cache_lookup_node(state: ChatState) -> Dict:
    """Serve a verified answer to an equivalent question, or pass the turn on."""
    if not cache_active(state):
        return {"cache": {"hit": False, "reason": "disabled"}}

    started = time.perf_counter()
    question = state.get("standalone_query") or state["query"]
    try:
        cache = get_answer_cache()
        query_vec = cache.embeddings.embed_query(question)
        result = cache.lookup(state["doc_id"], question, query_vector=query_vec,
                              model_id=state.get("model_id"))
    except JobTimeout:
        raise
    except Exception as exc:
        _log(state, f"[!] Answer cache unavailable ({type(exc).__name__}: {exc})")
        return {"cache": {"hit": False, "reason": "error"},
                "timings": add_timing(state, "cache_ms", started)}

    summary = result.summary()
    timings = add_timing(state, "cache_ms", started)

    if not result.hit:
        _log(state, f"[*] Cache miss ({result.outcome})")
        return {"query_vec": query_vec, "cache": summary, "timings": timings}

    payload = result.payload
    contexts = [Document(page_content=row.get("text", ""),
                         metadata={"page_number": row.get("page_number"),
                                   "chunk_index": row.get("chunk_index"),
                                   "doc_id": str(state["doc_id"])})
                for row in payload.get("contexts") or []]
    scores = [row.get("score") for row in payload.get("contexts") or []]
    reply = payload.get("answer", "")

    _log(state, f"[*] Cache hit (similarity {result.similarity:.3f}, verifier "
                f"{(result.verifier or 0):.2f}) -- reusing a verified answer")
    # Published the same way a freshly written reply is, so a client streaming the job
    # sees the answer arrive -- just a great deal sooner.
    _emit_token(state, reply)
    _emit_reply(state, reply, 1)

    verdict = {
        "task": "chat_msg",
        "score": payload.get("judge_score"),
        "passed": True,
        "reasoning": "Reused an answer the evaluator accepted for an equivalent question "
                     "about this document.",
        "regeneration_instruction": "",
        "threshold": state.get("threshold"),
        "cached": True,
    }
    return {
        "query_vec": query_vec,
        "cache": summary,
        "reply": reply,
        "verdict": verdict,
        "passed": True,
        "mode": "pdf",
        "contexts": contexts,
        "scores": scores,
        "top_score": payload.get("top_score") or 0.0,
        "retrieval": {"strategy": "cache", "basis": "cache",
                      "top_score": payload.get("top_score"),
                      "top_page": contexts[0].metadata.get("page_number") if contexts else None,
                      "top_chunk": contexts[0].metadata.get("chunk_index") if contexts else None},
        "timings": timings,
    }


def route_after_cache(state: ChatState) -> str:
    """A hit has its answer already; everything else retrieves."""
    return "persist" if (state.get("cache") or {}).get("hit") else "retrieve"


def cache_store_node(state: ChatState) -> Dict:
    """Offer the finished turn to the cache. Best effort, and silent on failure."""
    if not cache_active(state):
        return {}
    ok, reason = should_store(state)
    if not ok:
        return {}
    try:
        question = state.get("standalone_query") or state["query"]
        get_answer_cache().store(
            state["doc_id"], question, state.get("reply", ""),
            contexts=state.get("contexts") or [], scores=state.get("scores") or [],
            judge_score=(state.get("verdict") or {}).get("score"),
            top_score=state.get("top_score"), model_id=state.get("model_id"),
            query_vector=state.get("query_vec"))
        _log(state, "[*] Answer stored for reuse")
    except JobTimeout:
        raise
    except Exception as exc:
        _log(state, f"[!] Could not store the answer for reuse ({type(exc).__name__}: {exc})")
    return {}
