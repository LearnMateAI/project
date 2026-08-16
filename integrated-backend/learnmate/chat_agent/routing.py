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

    verdict = state.get("verdict") or {}
    score = verdict.get("score", 0)
    threshold = state.get("threshold", 70)
    critique = state.get("critique", "")

    if not critique or "failed to return a verdict" in critique:
        _log(state, "[*] Skipping retry (no actionable critique)")
        return "persist"

    if score < (threshold - 25):
        _log(state, f"[*] Skipping retry (score {score} is too far below threshold {threshold})")
        return "persist"

    _log(state, f"[*] Feedback: {critique}")
    return "generate"
