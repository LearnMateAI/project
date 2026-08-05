"""
Node 3 of 3: persist.

Stores the resource with its whole attempt trail.

The last attempt is the answer, pass or fail -- once a regeneration has run, its output is
what the caller gets. Earlier attempts stay in the record so a run that needed a retry,
and what the judge objected to the first time, remains answerable afterwards. That trail
is the data behind `cli.py stats`; keeping only the winner would make the question
"is the threshold set anywhere near right" unanswerable after the fact.
"""

from typing import Dict

from ..storage import content_store
from .helpers import _log
from .state import ResourceState


def persist_node(state: ResourceState) -> Dict:
    """Store the resource with its whole attempt trail."""
    attempts = state.get("attempts", [])
    final = attempts[-1] if attempts else {}

    # Off for evaluation runs and tests, which want the content without adding a row.
    if not state.get("persist", True):
        return {"content": final.get("content"), "resource_id": None}

    resource_id = content_store.save_resource(
        doc_id=state.get("doc_id"),
        task=state["task"],
        content=final.get("content"),
        accepted=bool(state.get("passed")),
        attempts=attempts,
        verdict=state.get("verdict"),
        source_preview=state.get("source", ""),
        params={"count": state.get("count"), "threshold": state["threshold"],
                "evaluated": state.get("evaluate", True)},
    )
    _log(state, f"[+] Stored resource {resource_id}")

    # `content` is republished from the last attempt so the caller always gets the text
    # that was actually stored, even when the run ended on a failure.
    return {"content": final.get("content"), "resource_id": str(resource_id)}
