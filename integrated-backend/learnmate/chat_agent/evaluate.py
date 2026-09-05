"""
Node 4 of 5: evaluate.

Hands the reply to the judge (a separate, deliberately different model -- see
learnmate/evaluator) and records the verdict.

Passing `contexts` through is what makes the grading strict: given contexts the judge
checks every claim against them and anything unsupported counts as a hallucination.
Given None it can only grade relevance, coherence and informativeness, which is the
right standard for a general-knowledge answer.

Three ways out of this node, cheapest first:

    evaluate=False   the caller wants no gate at all; auto-pass, nothing recorded
    gated            the judge would have nothing to check this reply against, so it is
                     not asked -- see gate.py, which is where the decision and the
                     measurement behind it live
    judged           the expensive path, and the only one that can start a retry

    reply (+ contexts)  -->  passed, verdict, critique, attempts
"""

import time
from typing import Dict

from ..evaluator.judge import get_judge
from ..evaluator.verdict import gated_verdict
from ..runtime_limits import add_timing
from ..storage import content_store
from . import gate
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
                              "verdict": None}],
                "timings": add_timing(state, "judge_ms", time.perf_counter())}

    # Cheaper than the judge by four orders of magnitude, and asked first: on a turn the
    # judge cannot say anything useful about, ~36s of second-model inference buys a number
    # that was never going to vary. See gate.py for which turns those are and the measured
    # reason why.
    skipped = gate.skip_reason(state)
    if skipped:
        verdict = gated_verdict("chat_msg", state["threshold"], skipped)
        # Logged like any other decision, with its own stage, so `stage_counts` shows how
        # often this fires and the score statistics do not silently become a survey of the
        # turns that happened to be judged.
        content_store.log_evaluation(
            "chat_msg", state["attempt"], None, True, state["threshold"],
            stage="gate", elapsed=0.0, doc_id=state.get("doc_id"),
            user_id=state.get("user_id"), extra={"mode": state.get("mode")})
        _log(state, "[*] Not scored (no source text to judge against)")
        return {
            "passed": True,
            "verdict": verdict,
            # Empty, not None: decide() reads the truthiness of the critique nowhere, but
            # generate does, and a stale instruction would rewrite an accepted reply.
            "critique": "",
            "attempts": [{"attempt": state["attempt"],
                          "reply": state.get("reply", ""), "verdict": verdict}],
            "timings": add_timing(state, "judge_ms", time.perf_counter()),
        }

    _log(state, "[*] Evaluating...")
    started = time.time()
    clock = time.perf_counter()

    contexts = state.get("contexts")
    if contexts:
        contexts = contexts[:2]
        
    query_to_judge = state.get("standalone_query") or state["query"]

    verdict = get_judge().judge_chat_reply(
        query_to_judge,                          # the standalone question resolves the history
        state.get("reply", ""),                  #   critique-padded one generate built
        contexts=contexts or None,               # capped at 2 chunks to save prefill
        history=None,                            # dropped because standalone_query resolves it
        threshold=state["threshold"],
    )

    # Every judgement is logged, including the ones that pass, so score distributions
    # and timings can be analysed later rather than only failures being visible.
    content_store.log_evaluation(
        "chat_msg", state["attempt"], verdict["score"], verdict["passed"],
        state["threshold"], stage="judge", elapsed=time.time() - started,
        doc_id=state.get("doc_id"), user_id=state.get("user_id"),
        extra={"mode": state.get("mode")})

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
        "timings": add_timing(state, "judge_ms", clock),
    }
