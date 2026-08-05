"""
Node 5 of 5: persist.

Records both halves of the turn in MongoDB. This is what makes the conversation outlive
the process: the next turn's `rewrite` node resolves pronouns against exactly what is
written here, so a session can be resumed later just by passing the same session_id.

    reply + verdict  -->  (two rows in Mongo)
"""

from typing import Dict

from ..storage import content_store
from .state import ChatState


def persist_node(state: ChatState) -> Dict:
    """Record the turn so the next one has history to resolve against."""
    # Off for evaluation runs and tests, which need the answer without polluting a real
    # conversation's history.
    if not state.get("persist", True):
        return {}

    session_id = state["session_id"]

    # The user turn is saved here rather than at the start of the graph so that a turn
    # which crashes mid-way leaves no half-record behind.
    content_store.save_turn(session_id, "user", state["query"], doc_id=state.get("doc_id"))

    # The assistant turn carries the audit trail alongside the text: how it was answered,
    # what it scored, whether it was accepted, how many tries it took, and which pages
    # of the PDF it drew on.
    content_store.save_turn(
        session_id, "assistant", state.get("reply", ""), doc_id=state.get("doc_id"),
        meta={
            "mode": state.get("mode"),
            "score": (state.get("verdict") or {}).get("score"),
            "accepted": bool(state.get("passed")),
            "attempts": len(state.get("attempts", [])),
            "pages": [doc.metadata.get("page_number") for doc in state.get("contexts") or []],
        })

    # Nothing to merge back -- this node's effect is entirely in the database.
    return {}
