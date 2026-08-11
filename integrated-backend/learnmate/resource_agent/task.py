"""
The contract every kind of study resource implements.

A Task owns everything type-specific and nothing else:

    system_prompt   who the model is being asked to be
    build_prompt    the user message, built from the passage and a count
    schema          the JSON shape, compiled into a decoding grammar by llama.cpp
    unwrap          parsed JSON -> the content itself
    render          the content -> plain text, for the judge and for display

Everything around it -- the model, the two evaluation gates, the retry contract,
persistence -- is shared, so adding a fifth kind of resource means adding one Task and
touching nothing else. The four that exist are one file each: mcq.py, practice_qsn.py,
keypoints.py, summary.py.
"""

from dataclasses import dataclass
from typing import Any, Callable, Dict


@dataclass(frozen=True)
class Task:
    """One kind of study resource. Frozen: a task definition is a constant."""

    name: str
    system_prompt: str
    schema: Dict[str, Any]
    build_prompt: Callable[[str, int], str]
    unwrap: Callable[[Any], Any]
    render: Callable[[Any], str]
    # What `count` means for this task, shown in CLI help. "questions" for the two
    # question types, "points" for key points, "sentences" for a summary.
    count_label: str = "items"


def unwrap_questions(data):
    """
    Pull the items out of a {"questions": [...]} envelope.

    Shared by mcq and practice_qsn, which differ in what each question contains but not
    in how the list is wrapped.

    Every schema in this package wraps its payload in an object rather than returning a
    bare array, because llama.cpp's grammar support is more reliable for a top-level
    object. Unwrapping is what hides that from the rest of the system. A model that
    ignored the envelope and returned the bare array anyway is still accepted -- there is
    no reason to fail an attempt whose content is right.
    """
    if isinstance(data, dict):
        return data.get("questions", [])
    return data if isinstance(data, list) else []
