"""
Gate 1: the structural dispatcher.

    validate(task, content)  ->  (ok, reasons)

Most bad generations fail mechanically rather than qualitatively: three options instead of
four, a correct_answer that appears in no option, an empty summary. Those are decidable in
plain Python in microseconds, and catching them here means the ~25 second judge call is
only ever spent on content that is already well-formed.

The rules themselves live next door -- mcq_rules.py and text_rules.py -- so this file is
only the map from a task name to its checker.
"""

from typing import Callable, Dict, List, Tuple

from .mcq_rules import validate_mcq, validate_mcq_set
from .text_rules import validate_keypoints, validate_practice_qsn, validate_summary

# task name -> the checker to run before calling the judge.
VALIDATORS: Dict[str, Callable] = {
    "mcq": validate_mcq_set,
    "practice_qsn": validate_practice_qsn,
    "keypoints": validate_keypoints,
    "summary": validate_summary,
}

__all__ = [
    "VALIDATORS",
    "validate",
    "validate_keypoints",
    "validate_mcq",
    "validate_mcq_set",
    "validate_practice_qsn",
    "validate_summary",
]


def validate(task: str, content) -> Tuple[bool, List[str]]:
    """
    Run the structural checker for `task`.

    An unknown task passes through rather than failing: a new resource type should reach
    the judge and be graded on its rubric, not be rejected for having no structural rules
    written for it yet. Note there is no "chat_msg" entry -- a chat reply is free prose
    with nothing mechanical to check, so it goes straight to gate 2.
    """
    checker = VALIDATORS.get(task)
    if checker is None:
        return True, []
    return checker(content)
