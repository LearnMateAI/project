"""
The state that flows between nodes across one generation run.

Same LangGraph rules as the chat agent: a node returns only the keys it wants to change
and the framework merges them, and a field opts out of overwrite-by-default with
`Annotated[type, reducer]`. `attempts` is the only field here that does.
"""

from typing import Any, Dict, List, Optional

from typing_extensions import Annotated, TypedDict


def _append(left: List, right: List) -> List:
    """Reducer: attempts accumulate across loop iterations instead of overwriting."""
    return (left or []) + (right or [])


class ResourceState(TypedDict, total=False):
    """One generation run's working memory."""

    # --- Inputs: set by generate_resource, never changed after ------------------------
    task: str            # "mcq", "summary", "keypoints", "practice_qsn"
    source: str          # the PDF passage, from ingestion.build_source_text
    count: int           # how many items -- or, for summary, roughly how many sentences
    doc_id: Any          # which document this came from, for the stored record
    threshold: int       # judge score out of 100 needed to pass
    max_attempts: int    # total generations allowed, including the first
    evaluate: bool       # False skips both gates
    persist: bool        # False returns the resource without storing it
    verbose: bool        # False silences progress logging

    # --- Written by generate ----------------------------------------------------------
    attempt: int         # 1-based counter of generations so far
    content: Any         # the parsed resource: a list of items, or a summary string
    started: float       # when this attempt began, for the timing in the evaluation log

    # --- Written by check -------------------------------------------------------------
    stage: str           # which gate decided this attempt: parse/validator/judge/skipped
    passed: bool         # did it clear both gates
    verdict: Optional[Dict]   # the judge's full result, None when a cheaper gate decided
    critique: Optional[str]   # what to fix, fed into the next generation
    previous: Any             # the rejected content, shown to the model on retry

    # --- Written by persist -----------------------------------------------------------
    resource_id: Optional[str]

    # The one accumulating field: the audit trail of the whole run. `content` keeps only
    # the newest attempt; this keeps every attempt with the reason it was rejected, which
    # is what makes a bad run answerable afterwards instead of guessed at.
    attempts: Annotated[List[Dict], _append]
