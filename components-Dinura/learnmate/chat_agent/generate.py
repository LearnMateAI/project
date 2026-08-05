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
from .helpers import _as_messages, _log
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
        # Low but non-zero temperature: enough variation that a regeneration can differ
        # from the reply the judge just rejected, not so much that it drifts.
        reply = get_generator_llm().invoke(messages, temperature=0.3, max_tokens=512)
        return {"attempt": attempt, "reply": (reply.content or "").strip()}
    except Exception as exc:
        # Return an empty reply rather than raising: the graph continues, the judge
        # scores the emptiness badly, and the retry loop gets a chance to recover.
        _log(state, f"[!] Generation failed: {exc}")
        return {"attempt": attempt, "reply": ""}
