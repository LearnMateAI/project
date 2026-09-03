"""
Node 1 of 5: rewrite.

Resolves a follow-up question into a standalone one, so that retrieval embeds something
meaningful.

Why this runs *before* retrieval rather than after: "what about his powers?" embeds to
almost nothing useful, and retrieving on the pronoun returns noise. Resolved against the
history into "what are the President's powers?" it retrieves correctly. Doing it the
other way round means the retrieval has already failed by the time we fix the query.

    query + history  -->  standalone_query
"""

import re
import time
from typing import Dict

from langchain_core.messages import HumanMessage, SystemMessage

from ..llm import get_judge_llm
from ..runtime_limits import JobTimeout, add_timing
from .helpers import _log
from .prompts import REWRITE_SYSTEM
from .state import ChatState

def _needs_rewrite(query: str, history: list) -> bool:
    if not history:
        return False
    query_lower = query.lower()
    if len(query.split()) <= 4:
        return True
    if re.match(r"^(it|this|that|he|she|his|her|they|their|what about|why)\b", query_lower):
        return True
    last_turn = history[-1]["content"].lower()
    q_words = set(re.findall(r"\w+", query_lower))
    l_words = set(re.findall(r"\w+", last_turn))
    if len(q_words.intersection(l_words)) < 1:
        return True
    return False

def rewrite_node(state: ChatState) -> Dict:
    """Resolve follow-up references so retrieval sees a self-contained question."""
    started = time.perf_counter()
    query = state["query"]
    history = state.get("history") or []

    if not _needs_rewrite(query, history):
        return {"standalone_query": query,
                "timings": add_timing(state, "rewrite_ms", started)}

    history_text = "\n".join(f"{turn['role']}: {turn['content']}" for turn in history)
    messages = [
        SystemMessage(content=REWRITE_SYSTEM),
        HumanMessage(content=f"Conversation history:\n{history_text}\n\n"
                             f"Follow-up question: {query}"),
    ]

    try:
        # Temperature 0: this is a mechanical transformation, not a creative one.
        # max_tokens is small because the output should be a single question -- capping
        # it also stops a chatty model from appending an explanation.
        reply = get_judge_llm().invoke(messages, temperature=0.0, max_tokens=100)
        rewritten = (reply.content or "").strip()

        # Only log when it actually changed something, to keep the CLI output quiet
        # for the common case of an already-standalone question.
        if rewritten and rewritten != query:
            _log(state, f"[*] Rewritten: {rewritten}")

        return {"standalone_query": rewritten or query,
                "timings": add_timing(state, "rewrite_ms", started)}
    except JobTimeout:
        raise
    except Exception:
        # Rewriting is an optimisation; the raw query still retrieves something.
        # A failure here must never cost the user their answer.
        return {"standalone_query": query,
                "timings": add_timing(state, "rewrite_ms", started)}

