"""
Node 3 of 3: persist.

Stores the resource with its whole attempt trail.

The *best-scoring* attempt is the answer -- the same policy as chat. A retry exists to
improve the resource, and when it scores worse the better attempt is still sitting in
`attempts`. Earlier attempts stay in the record so a run that needed a retry, and what
the judge objected to the first time, remains answerable afterwards. That trail is the
data behind content_store.evaluation_stats(); keeping only the winner would make the
question "is the threshold set anywhere near right" unanswerable after the fact.
"""

from typing import Dict, Optional, Tuple

from ..storage import content_store
from .helpers import _log
from .state import ResourceState


def _score_of(attempt: Dict) -> Optional[int]:
    """The judged score of one attempt, or None when it was never judged."""
    score = attempt.get("score")
    if isinstance(score, int):
        return score
    verdict = attempt.get("verdict")
    if not verdict:
        return None
    value = verdict.get("score")
    return value if isinstance(value, int) else None


def best_attempt(state: ResourceState) -> Tuple[object, Optional[Dict], bool]:
    """
    The attempt the run should end on, as (content, verdict, passed).

    `generate` overwrites `state["content"]` on every pass, so after a regeneration the
    newest text is the only one left -- even when the judge scored it worse. Falls back
    to the last attempt when ranking is meaningless (evaluation off, or no usable score).
    """
    attempts = state.get("attempts") or []
    if not attempts:
        return state.get("content"), state.get("verdict"), bool(state.get("passed"))

    ranked = [(attempt, _score_of(attempt)) for attempt in attempts]
    scored = [(attempt, score) for attempt, score in ranked if score is not None]

    if not scored:
        last = attempts[-1]
        return last.get("content"), last.get("verdict"), bool(state.get("passed"))

    chosen, score = max(scored, key=lambda pair: pair[1])
    verdict = chosen.get("verdict") or state.get("verdict")
    passed = bool(chosen.get("passed")) if "passed" in chosen else (
        score >= state.get("threshold", 0)
    )

    if chosen is not attempts[-1]:
        _log(state, f"[*] Keeping attempt {chosen.get('attempt')} (scored {score}) over "
                    f"the later one (scored {_score_of(attempts[-1])})")

    return chosen.get("content"), verdict, passed


def persist_node(state: ResourceState) -> Dict:
    """Store the resource with its whole attempt trail."""
    content, verdict, passed = best_attempt(state)
    selection = {"content": content, "verdict": verdict, "passed": passed}

    # Off for evaluation runs and tests, which want the content without adding a row.
    if not state.get("persist", True):
        return {**selection, "resource_id": None}

    resource_id = content_store.save_resource(
        doc_id=state.get("doc_id"),
        user_id=state.get("user_id"),
        task=state["task"],
        content=content,
        accepted=bool(passed),
        attempts=state.get("attempts", []),
        verdict=verdict,
        source_preview=state.get("source", ""),
        params={"count": state.get("count"), "threshold": state["threshold"],
                "evaluated": state.get("evaluate", True),
                "summary_style": state.get("summary_style"),
                "difficulty": state.get("difficulty"),
                "model_id": state.get("model_id"),
                "topic": state.get("topic")},
    )
    _log(state, f"[+] Stored resource {resource_id}")

    return {**selection, "resource_id": str(resource_id)}
