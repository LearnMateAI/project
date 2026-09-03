"""
The public entry point: generate one study resource end to end.

    build_source_text(doc_id, topic=...)   <- ingestion, picks the passage
              |
              v
    generate_resource("mcq", source, count=5)
              |
              v
    {task, content, accepted, verdict, attempts, resource_id, timings}
"""

from typing import Dict
import logging

from .. import config
from .graph import get_resource_graph
from .mcq import resolve_difficulty
from .state import ResourceState
from .summary import resolve_summary_style
from .tasks import get_task

logger = logging.getLogger("learnmate.resource")


def generate_resource(task: str, source: str, count: int = 5, doc_id=None,
                      threshold: int = None, max_attempts: int = None,
                      evaluate: bool = True, persist: bool = True,
                      verbose: bool = True, user_id: str = None,
                      on_progress=None, summary_style: str = None,
                      difficulty: str = None, model_id: str = None,
                      topic: str = None) -> Dict:
    """
    Generate one study resource end to end.

    task    -- "mcq", "practice_qsn", "keypoints" or "summary"
    source  -- the PDF passage, from ingestion.build_source_text
    count   -- how many items; for a summary, roughly how many sentences
    user_id -- who asked; stored on the resource so one student's listing never returns
               another's work from the same shared PDF
    on_progress -- optional callable(message) called as each attempt starts, so a caller
               running this on a job queue can report what it is doing

    Returns {task, content, accepted, verdict, attempts, resource_id, timings}, where
    `content` is the best-scoring attempt and `attempts` holds the whole trail in order.
    `accepted` is False when the run ended on a rejection, and the content is returned
    anyway so the caller can show it with a warning rather than nothing at all.
    """
    get_task(task)  # fail fast on an unknown task, before loading any model

    if not (source or "").strip():
        raise ValueError("Cannot generate from empty source text.")

    initial: ResourceState = {
        "task": task,
        "source": source,
        "count": count,
        "doc_id": doc_id,
        "user_id": user_id,
        "on_progress": on_progress,
        # `is not None` rather than `or`: threshold=0 means "accept anything".
        "threshold": threshold if threshold is not None else config.EVALUATOR_THRESHOLD,
        "max_attempts": max_attempts or config.MAX_ATTEMPTS,
        "evaluate": evaluate,
        "persist": persist,
        "verbose": verbose,
        "attempt": 0,
        "attempts": [],
        "summary_style": resolve_summary_style(source, summary_style) if task == "summary"
                         else None,
        "difficulty": resolve_difficulty(difficulty) if task == "mcq" else None,
        "model_id": model_id,
        "topic": topic,
    }

    # The graph loops, so LangGraph's default recursion budget has to cover
    # attempts x (generate + check) plus persist.
    limit = 2 * initial["max_attempts"] + 4
    final = get_resource_graph().invoke(initial, {"recursion_limit": limit})
    timings = final.get("timings") or {}
    logger.info(
        "resource timings task=%s generate_ms=%s judge_ms=%s model_load_ms=%s",
        task,
        timings.get("generate_ms"),
        timings.get("judge_ms"),
        timings.get("model_load_ms"),
    )

    return {
        "task": task,
        "content": final.get("content"),
        "accepted": bool(final.get("passed")),
        "verdict": final.get("verdict"),
        "attempts": final.get("attempts", []),
        "resource_id": final.get("resource_id"),
        "timings": timings,
    }
