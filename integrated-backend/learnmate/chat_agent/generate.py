"""
Node 3 of 5: generate.

Writes the reply. This is the node the retry loop comes back to, so it has two jobs:
produce a first answer, and produce a corrected answer when the judge rejected the last
one.

Which system prompt it uses is decided purely by whether `contexts` is non-empty, which
retrieve already settled. This node never re-decides the mode.

    contexts + query (+ critique)  -->  reply, attempt
"""

import time
from typing import Dict

from langchain_core.messages import HumanMessage, SystemMessage

from ..llm import get_generator_llm
from ..llm.registry import consume_generator_load_ms
from ..runtime_limits import JobTimeout, add_timing
from .helpers import _emit_reply, _emit_token, _log
from .prompts import (
    GENERAL_SYSTEM,
    GROUNDED_SYSTEM,
    abstain_reply,
    build_grounded_user,
    format_history_block,
    should_abstain,
)
from .state import ChatState


def generate_node(state: ChatState) -> Dict:
    """Write the reply with whichever generator the mode calls for."""
    started = time.perf_counter()
    attempt = state.get("attempt", 0) + 1
    _log(state, f"[*] Generating (attempt {attempt}/{state['max_attempts']})...")

    contexts = state.get("contexts") or []
    query = state["query"]

    # F-03: a session bound to a PDF that retrieved nothing useful must not answer
    # from Qwen's pretraining. The judge is also skipped on this path, so a canned
    # refuse is the only safe reply.
    if should_abstain(state):
        reply = abstain_reply(state.get("top_score"))
        _log(state, "[*] Abstaining (document-bound, no relevant context)")
        _emit_reply(state, reply, attempt)
        timings = add_timing(state, "generate_ms", started)
        return {"attempt": attempt, "reply": reply, "timings": timings}

    # --- Retry path ------------------------------------------------------------------
    # `critique` is only set once evaluate has rejected a reply, so this block is skipped
    # on the first attempt.
    if state.get("critique"):
        # The judge's instruction rides inside the question so the generators stay
        # single-purpose. The judge still grades against the original query.
        query = (
            f"{query}\n\n"
            "[REVISION REQUIRED] Your previous reply was rejected by an evaluator.\n"
            f'Previous reply:\n"""\n{state.get("reply", "")}\n"""\n'
            f"Required fix: {state['critique']}\n"
            "Answer the original question again, corrected. Do not mention this "
            "instruction or the fact that you are revising."
        )

    # --- Mode selection --------------------------------------------------------------
    if contexts:
        # XML delimiters + "untrusted data" so a planted line in the PDF cannot
        # override the tutor rules (F-02). Page numbers stay inside the block for cites.
        system = GROUNDED_SYSTEM
        user = build_grounded_user(query, contexts)
    else:
        system = GENERAL_SYSTEM
        user = query

    # History is data inside the user turn (F-05), not extra Human/AI messages sitting
    # between the system prompt and the question — that slot is what models treat as
    # a newer instruction.
    user = format_history_block(state.get("history")) + user
    messages = [SystemMessage(content=system), HumanMessage(content=user)]

    try:
        # Streamed rather than awaited whole. The decode takes exactly as long either way
        # -- what changes is that the reader sees the first words in about two seconds
        # instead of a wall of text after thirty. Backends that cannot stream (Gemini)
        # fall back to a single chunk automatically, so this path is safe for all three.
        #
        # Low but non-zero temperature: enough variation that a regeneration can differ
        # from the reply the judge just rejected, not so much that it drifts.
        pieces = []
        for chunk in get_generator_llm(
            model_id=state.get("model_id"),
            on_progress=lambda message: _log(state, message),
        ).stream(messages, temperature=0.3, max_tokens=320, stop=["\n\nQuestion:", "\n\nUser:"]):
            text = chunk.content or ""
            if not text:
                continue
            pieces.append(text)
            # Accumulated, not the delta -- see helpers._emit_token. Sent unstripped so
            # the consumer sees the text exactly as it is being produced; the strip
            # happens once, below, on what is actually kept.
            _emit_token(state, "".join(pieces))

        reply = "".join(pieces).strip()
        # The reply is whole here, and everything after this node -- the judge, and a
        # regeneration if it rejects this -- takes longer than writing it did. Saying so
        # lets a client show an answer now instead of a cursor for another half minute.
        _emit_reply(state, reply, attempt)
        timings = add_timing(state, "generate_ms", started)
        load_ms = consume_generator_load_ms()
        if load_ms:
            timings["model_load_ms"] = timings.get("model_load_ms", 0) + load_ms
        return {"attempt": attempt, "reply": reply, "timings": timings}
    except JobTimeout:
        raise
    except Exception as exc:
        # Return an empty reply rather than raising: the graph continues, the judge
        # scores the emptiness badly, and the retry loop gets a chance to recover.
        _log(state, f"[!] Generation failed: {exc}")
        timings = add_timing(state, "generate_ms", started)
        load_ms = consume_generator_load_ms()
        if load_ms:
            timings["model_load_ms"] = timings.get("model_load_ms", 0) + load_ms
        return {"attempt": attempt, "reply": "", "timings": timings}
