"""
Node 2 of 3: check. Both evaluation gates, cheapest first.

    gate 1  validators.validate()   plain Python, microseconds
    gate 2  the LLM judge           ~25 seconds

Most bad generations fail mechanically -- three options instead of four, a correct_answer
in none of them, an empty summary -- so the judge is only ever spent on content that is
already well-formed. `stage` records which gate decided the attempt, and that is what
content_store.stage_counts() groups by: if the validator is deciding most attempts, the
generation prompt needs work, not the threshold.

    content  ->  passed, stage, verdict, critique
"""

import time
from typing import Dict

from ..evaluator import validators
from ..evaluator.judge import get_judge
from ..storage import content_store
from .helpers import _log
from .state import ResourceState
from .tasks import get_task


def check_node(state: ResourceState) -> Dict:
    """Structural gate, then the judge. The judge only sees content that passed the gate."""
    # Generation itself failed; there is no content to check and generate_node has
    # already recorded the attempt.
    if state.get("stage") == "parse":
        return {}

    task = get_task(state["task"])
    attempt = state["attempt"]
    content = state.get("content")
    started = state.get("started", time.time())

    # --- Gate 1: structural ----------------------------------------------------------
    ok, reasons = validators.validate(task.name, content)
    if not ok:
        _log(state, f"[*] Structural check FAILED: {'; '.join(reasons)}")
        content_store.log_evaluation(
            task.name, attempt, None, False, state["threshold"], stage="validator",
            elapsed=time.time() - started, doc_id=state.get("doc_id"),
            extra={"reasons": reasons})
        return {
            "stage": "validator",
            "passed": False,
            "verdict": None,
            # The validator's reasons are already phrased as faults, so they become the
            # regeneration instruction directly -- no judge call needed to say what broke.
            "critique": "Fix these structural problems and change nothing else: "
                        + "; ".join(reasons),
            "previous": content,
            "attempts": [{"attempt": attempt, "stage": "validator", "passed": False,
                          "score": None, "reasons": reasons, "content": content}],
        }

    # --- Evaluation switched off ------------------------------------------------------
    # Generation is intact and both gates are skipped, which is how you measure what
    # evaluation is actually costing.
    if not state.get("evaluate", True):
        return {
            "stage": "skipped", "passed": True, "verdict": None, "critique": None,
            "attempts": [{"attempt": attempt, "stage": "skipped", "passed": True,
                          "score": None, "reasons": [], "content": content}],
        }

    # --- Gate 2: the judge ------------------------------------------------------------
    _log(state, "[*] Structural check passed. Judging...")
    verdict = get_judge().judge(
        task.name, task.render(content), source=state["source"],
        threshold=state["threshold"])

    content_store.log_evaluation(
        task.name, attempt, verdict["score"], verdict["passed"], state["threshold"],
        stage="judge", elapsed=time.time() - started, doc_id=state.get("doc_id"))
    _log(state, f"[*] Score {verdict['score']}/100 -> "
                f"{'PASS' if verdict['passed'] else 'REGENERATE'}")

    return {
        "stage": "judge",
        "passed": verdict["passed"],
        "verdict": verdict,
        "critique": verdict["regeneration_instruction"],
        "previous": content,
        "attempts": [{"attempt": attempt, "stage": "judge", "passed": verdict["passed"],
                      "score": verdict["score"], "reasons": [], "content": content,
                      "verdict": verdict}],
    }
