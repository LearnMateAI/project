"""
Node 3 of 5: generate.

Writes the reply. This is the node the retry loop comes back to, so it has two jobs:
produce a first answer, and produce a corrected answer when the judge rejected the last
one.

Which system prompt it uses is decided purely by whether `contexts` is non-empty, which
retrieve already settled. This node never re-decides the mode.

    contexts + query (+ critique)  -->  reply, attempt
"""

from typing import Dict

from langchain_core.messages import HumanMessage, SystemMessage

from ..llm import get_generator_llm
from .helpers import _as_messages, _emit_reply, _emit_token, _log
from .prompts import GENERAL_SYSTEM, GROUNDED_SYSTEM
from .state import ChatState


def generate_node(state: ChatState) -> Dict:
    """Write the reply with whichever generator the mode calls for."""
    attempt = state.get("attempt", 0) + 1
    _log(state, f"[*] Generating (attempt {attempt}/{state['max_attempts']})...")

    contexts = state.get("contexts") or []
    query = state["query"]

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
        # Page numbers are prefixed so the model can cite them and so the metadata
        # survives into persist for the "which pages was this from" record.
        context_text = "\n\n".join(
            f"Page {doc.metadata.get('page_number', 'N/A')}: {doc.page_content}"
            for doc in contexts)
        system = GROUNDED_SYSTEM
        user = f"Context:\n{context_text}\n\nQuestion: {query}"
    else:
        system = GENERAL_SYSTEM
        user = query

    # History goes between the system prompt and the current question so the model reads
    # the conversation in the order it happened.
    messages = [SystemMessage(content=system), *_as_messages(state.get("history")),
                HumanMessage(content=user)]

    try:
        # Streamed rather than awaited whole. The decode takes exactly as long either way
        # -- what changes is that the reader sees the first words in about two seconds
        # instead of a wall of text after thirty. Backends that cannot stream (Gemini)
        # fall back to a single chunk automatically, so this path is safe for all three.
        #
        # Low but non-zero temperature: enough variation that a regeneration can differ
        # from the reply the judge just rejected, not so much that it drifts.
        pieces = []
        for chunk in get_generator_llm().stream(messages, temperature=0.3, max_tokens=320, stop=["\n\nQuestion:", "\n\nUser:"]):
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
        return {"attempt": attempt, "reply": reply}
    except Exception as exc:
        # Return an empty reply rather than raising: the graph continues, the judge
        # scores the emptiness badly, and the retry loop gets a chance to recover.
        _log(state, f"[!] Generation failed: {exc}")
        return {"attempt": attempt, "reply": ""}
