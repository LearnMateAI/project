"""Live evaluator surface. Per-model folders inject a candidate llm into Judge."""

from learnmate.evaluator.judge import Judge, get_judge
from learnmate.evaluator.rubrics import for_task
from learnmate.evaluator.validators import validate

__all__ = ["Judge", "get_judge", "for_task", "validate"]
