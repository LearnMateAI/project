"""
The conditional edge out of evaluate -- the only branch in the graph.

This is not a node: it returns the *name* of where to go next rather than a state
update. graph.py maps those names onto real nodes.

    passed?          -> persist
    out of attempts? -> persist anyway
    otherwise        -> back to generate, carrying the critique
"""

from .helpers import _log
from .state import ChatState


def decide(state: ChatState) -> str:
    """Choose between accepting the reply and regenerating it."""
    if state.get("passed"):
        return "persist"

    # The budget is spent. Persist the failed reply anyway and let `accepted` tell the
    # caller it was not reviewed clean -- a user mid-conversation needs an answer more
    # than they need silence.
    if state["attempt"] >= state["max_attempts"]:
        return "persist"

    _log(state, f"[*] Feedback: {state.get('critique')}")
    return "generate"
