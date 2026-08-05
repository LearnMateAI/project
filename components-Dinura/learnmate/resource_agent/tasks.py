"""
The registry of resource types.

One entry per kind of study resource that can be generated from a PDF passage. Adding a
fifth means writing one module beside the four below and adding a line here -- the graph,
the gates and the CLI all read this map rather than naming tasks themselves.

    mcq           multiple-choice questions      -> mcq.py
    practice_qsn  short-answer questions         -> practice_qsn.py
    keypoints     a list of key points           -> keypoints.py
    summary       one block of connected prose   -> summary.py

Each task name here must also appear in evaluator/validators.py (its structural gate) and
evaluator/rubrics.py (its grading criteria). A task missing from either still runs -- the
validator passes anything unknown through and the judge falls back to the generic
rubric -- but it is then being graded far more loosely than the other four.
"""

from typing import Dict, List

from .keypoints import KEYPOINTS
from .mcq import MCQ
from .practice_qsn import PRACTICE_QSN
from .summary import SUMMARY
from .task import Task

TASKS: Dict[str, Task] = {
    "mcq": MCQ,
    "practice_qsn": PRACTICE_QSN,
    "keypoints": KEYPOINTS,
    "summary": SUMMARY,
}

# Sorted so the CLI's --help and its `choices` list are stable between runs.
TASK_NAMES: List[str] = sorted(TASKS)

__all__ = ["TASKS", "TASK_NAMES", "Task", "get_task", "render"]


def get_task(name: str) -> Task:
    """Look up a task, naming the alternatives when it misses."""
    task = TASKS.get(name)
    if task is None:
        raise ValueError(f"Unknown task {name!r}; expected one of {TASK_NAMES}")
    return task


def render(task_name: str, content) -> str:
    """Flatten generated content into the plain text the judge grades."""
    task = TASKS.get(task_name)
    return task.render(content) if task else str(content)
