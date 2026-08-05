"""
The conditional edge out of check -- the only branch in the graph.

    passed?          -> persist
    out of attempts? -> persist anyway
    otherwise        -> back to generate, carrying the critique

The budget is 2: one generation plus one regeneration. Raising it is not just slower -- a
3B judge tends to oscillate rather than converge over more rounds, and the third attempt
is usually a worse version of the first.
"""

from .helpers import _log
from .state import ResourceState


def decide(state: ResourceState) -> str:
    """Stop on a pass or on the attempt budget; otherwise go round again."""
    if state.get("passed"):
        return "persist"
    if state["attempt"] >= state["max_attempts"]:
        return "persist"
    _log(state, f"[*] Feedback: {state.get('critique')}")
    return "generate"
