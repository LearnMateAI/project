"""
Node 5 of 5: persist.

Two jobs, in this order: pick which attempt the turn actually ends on, then record both
halves of it in MongoDB. This is what makes the conversation outlive the process: the
next turn's `rewrite` node resolves pronouns against exactly what is written here, so a
session can be resumed later just by passing the same session_id.

    attempts  -->  the best reply + its verdict  -->  (two rows in Mongo)

The selection has to happen here rather than in `generate`, because "best" is only knowable
once every attempt has been judged -- and this is the one node every path reaches.
"""

from typing import Dict, Optional, Tuple

from ..storage import content_store
from .helpers import _log
from .state import ChatState


def _score_of(attempt: Dict) -> Optional[int]:
    """The judged score of one attempt, or None when it was never judged."""
    verdict = attempt.get("verdict")
    if not verdict:
        return None
    score = verdict.get("score")
    return score if isinstance(score, int) else None


def best_attempt(state: ChatState) -> Tuple[str, Optional[Dict], bool]:
    """
    The attempt the turn should end on, as (reply, verdict, passed).

    `generate` overwrites `state["reply"]` on every pass, so after a regeneration the
    newest text is the only one left -- even when the judge scored it *worse* than the
    attempt it replaced. That is the wrong answer to hand a student: the retry exists to
    improve the reply, and when it fails to, the better attempt is still sitting in
    `attempts` with its verdict attached.

    Falls back to the last attempt whenever ranking is meaningless -- evaluation switched
    off, or a judge that returned no usable score -- which keeps the un-judged path
    behaving exactly as it did before.
    """
    attempts = state.get("attempts") or []
    if not attempts:
        # No attempt was ever recorded (generation raised before evaluate ran). Whatever
        # is on the state is all there is.
        return state.get("reply", ""), state.get("verdict"), bool(state.get("passed"))

    scored = [(attempt, _score_of(attempt)) for attempt in attempts]
    ranked = [(attempt, score) for attempt, score in scored if score is not None]

    if not ranked:
        last = attempts[-1]
        return last.get("reply", ""), last.get("verdict"), bool(state.get("passed"))

    # max() keeps the first of any tie, which is the earliest attempt -- the right choice
    # when a regeneration merely matched the reply it was supposed to improve on.
    chosen, score = max(ranked, key=lambda pair: pair[1])
    verdict = chosen.get("verdict") or {}
    passed = score >= state.get("threshold", 0)

    if chosen is not attempts[-1]:
        _log(state, f"[*] Keeping attempt {chosen.get('attempt')} (scored {score}) over "
                    f"the later one (scored {_score_of(attempts[-1])})")

    return chosen.get("reply", ""), verdict, passed


def persist_node(state: ChatState) -> Dict:
    """Settle on the best attempt, then record the turn."""
    reply, verdict, passed = best_attempt(state)

    # Merged back into the state so `ChatAgent.ask` returns the same reply that was
    # stored. Returned even when persistence is off, because the selection is about what
    # the *caller* gets, not about the database.
    selection = {"reply": reply, "verdict": verdict, "passed": passed}

    # Off for evaluation runs and tests, which need the answer without polluting a real
    # conversation's history.
    if not state.get("persist", True):
        return selection

    session_id = state["session_id"]
    user_id = state.get("user_id")

    # The user turn is saved here rather than at the start of the graph so that a turn
    # which crashes mid-way leaves no half-record behind.
    content_store.save_turn(session_id, "user", state["query"],
                            doc_id=state.get("doc_id"), user_id=user_id)

    # The assistant turn carries the audit trail alongside the text: how it was answered,
    # what it scored, whether it was accepted, how many tries it took, and which pages
    # of the PDF it drew on.
    content_store.save_turn(
        session_id, "assistant", reply, doc_id=state.get("doc_id"),
        user_id=user_id,
        meta={
            "mode": state.get("mode"),
            "score": (verdict or {}).get("score"),
            "accepted": bool(passed),
            # Every generation that ran, not the index of the one kept -- this is the cost
            # of the turn, and it stays honest when an earlier attempt won.
            "attempts": len(state.get("attempts", [])),
            "pages": [doc.metadata.get("page_number") for doc in state.get("contexts") or []],
        })

    return selection
