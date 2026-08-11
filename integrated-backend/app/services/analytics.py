"""
What one user has done, and how well it scored.

Two halves, and the second is the interesting one:

    activity   how many documents, resources, conversations and turns
    quality    the score distribution from the evaluation log

The quality half exists because this system grades its own output. Every generation is
scored by a separate judge model and every verdict is logged -- passes as well as
failures -- so "how good is the material this produced" is a question with an actual
answer rather than an impression.

`stages` is the diagnostic worth reading. It says which gate decided each attempt:

    parse      the generator's output could not be read as JSON at all
    validator  structural checks rejected it without the judge running
    judge      the model scored it
    skipped    evaluation was switched off

A `validator` count that dominates means the generation prompt needs work, not the
threshold. That distinction is invisible from a pass rate alone.
"""

from typing import Dict

from learnmate import config as engine_config
from learnmate.storage import content_store, ownership


def overview(user_id: str) -> Dict:
    """Everything the analytics page shows, in one call."""
    by_task = content_store.count_by_task(user_id)

    total = sum(entry["total"] for entry in by_task.values())
    accepted = sum(entry["accepted"] for entry in by_task.values())

    return {
        "documents": ownership.count_links(user_id),
        "sessions": content_store.count_user_sessions(user_id),
        "messages": content_store.count_turns(user_id),
        "questions_asked": content_store.count_turns(user_id, role="user"),
        "resources": {
            "total": total,
            "accepted": accepted,
            # None rather than 0 when nothing has been generated: "no data" and "nothing
            # passed" are different, and rounding the first to the second is a lie.
            "acceptance_rate": round(accepted / total, 3) if total else None,
            "by_type": by_task,
        },
        "evaluation": {
            "threshold": engine_config.EVALUATOR_THRESHOLD,
            # Per task: n, min, median, max, mean, distinct, pass_rate. `distinct` is the
            # one that says whether the judge can separate good from bad at all -- scores
            # clustered in a narrow band cannot, at any threshold.
            "scores": content_store.evaluation_stats(user_id=user_id),
            "stages": content_store.stage_counts(user_id=user_id),
        },
    }
