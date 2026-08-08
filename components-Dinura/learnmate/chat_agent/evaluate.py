"""
Node 4 of 5: evaluate.

Hands the reply to the judge (a separate, deliberately different model -- see
learnmate/evaluator) and records the verdict.

Passing `contexts` through is what makes the grading strict: given contexts the judge
checks every claim against them and anything unsupported counts as a hallucination.
Given None it can only grade relevance, coherence and informativeness, which is the
right standard for a general-knowledge answer.

    reply (+ contexts)  -->  passed, verdict, critique, attempts
"""

import time
from typing import Dict

from ..evaluator.judge import get_judge
from ..storage import content_store
from .helpers import _log
from .state import ChatState


def evaluate_node(state: ChatState) -> Dict:
    """Judge the reply, strictly when it was supposed to be grounded."""
    # Escape hatch for callers that want raw generation speed, or that are running
    # without the judge model available. Auto-passing here means decide() routes
    # straight to persist and the retry loop never runs.
    if not state.get("evaluate", True):
        return {"passed": True, "verdict": None,
                "attempts": [{"attempt": state["attempt"], "reply": state.get("reply", ""),
                              "verdict": None}]}

    _log(state, "[*] Evaluating...")
    started = time.time()

    verdict = get_judge().judge_chat_reply(
        state["query"],                          # the original question, not the
        state.get("reply", ""),                  #   critique-padded one generate built
        contexts=state.get("contexts") or None,  # None here switches the judge's rubric
        history=state.get("history"),
        threshold=state["threshold"],
    )

    # Every judgement is logged, including the ones that pass, so score distributions
    # and timings can be analysed later rather than only failures being visible.
    content_store.log_evaluation(
        "chat_msg", state["attempt"], verdict["score"], verdict["passed"],
        state["threshold"], stage="judge", elapsed=time.time() - started,
        doc_id=state.get("doc_id"), extra={"mode": state.get("mode")})

    _log(state, f"[*] Score {verdict['score']}/100 -> "
                f"{'PASS' if verdict['passed'] else 'REGENERATE'}")

    return {
        "passed": verdict["passed"],
        "verdict": verdict,
        # Read by generate on the next pass through the loop.
        "critique": verdict["regeneration_instruction"],
        # Appended, not overwritten -- see the reducer on `attempts` in state.py.
        "attempts": [{"attempt": state["attempt"], "reply": state.get("reply", ""),
                      "verdict": verdict}],
    }
