"""
The public entry point: generate one study resource end to end.

    build_source_text(doc_id, topic=...)   <- ingestion, picks the passage
              |
              v
    generate_resource("mcq", source, count=5)
              |
              v
    {task, content, accepted, verdict, attempts, resource_id}
"""

from typing import Dict

from .. import config
from .graph import get_resource_graph
from .state import ResourceState
from .tasks import get_task


def generate_resource(task: str, source: str, count: int = 5, doc_id=None,
                      threshold: int = None, max_attempts: int = None,
                      evaluate: bool = True, persist: bool = True,
                      verbose: bool = True) -> Dict:
    """
    Generate one study resource end to end.

    task    -- "mcq", "practice_qsn", "keypoints" or "summary"
    source  -- the PDF passage, from ingestion.build_source_text
    count   -- how many items; for a summary, roughly how many sentences

    Returns {task, content, accepted, verdict, attempts, resource_id}, where `content` is
    the last attempt and `attempts` holds the whole trail in order. `accepted` is False
    when the run ended on a rejection, and the content is returned anyway so the caller
    can show it with a warning rather than nothing at all.
    """
    get_task(task)  # fail fast on an unknown task, before loading any model

    if not (source or "").strip():
        raise ValueError("Cannot generate from empty source text.")

    initial: ResourceState = {
        "task": task,
        "source": source,
        "count": count,
        "doc_id": doc_id,
        # `is not None` rather than `or`: threshold=0 means "accept anything".
        "threshold": threshold if threshold is not None else config.EVALUATOR_THRESHOLD,
        "max_attempts": max_attempts or config.MAX_ATTEMPTS,
        "evaluate": evaluate,
        "persist": persist,
        "verbose": verbose,
        "attempt": 0,
        "attempts": [],
    }

    # The graph loops, so LangGraph's default recursion budget has to cover
    # attempts x (generate + check) plus persist.
    limit = 2 * initial["max_attempts"] + 4
    final = get_resource_graph().invoke(initial, {"recursion_limit": limit})

    return {
        "task": task,
        "content": final.get("content"),
        "accepted": bool(final.get("passed")),
        "verdict": final.get("verdict"),
        "attempts": final.get("attempts", []),
        "resource_id": final.get("resource_id"),
    }
