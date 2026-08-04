"""
The evaluator agent: two gates over generated content.

    validators.py   deterministic structural checks, microseconds
    judge.py        an LLM rubric grade, ~25 seconds

Cheapest first. Most bad generations fail mechanically, so the judge is only ever spent
on content that is already well-formed.
"""

from . import rubrics, validators
from .judge import VERDICT_SCHEMA, Judge, get_judge, parse_verdict
from .validators import validate

__all__ = [
    "Judge",
    "VERDICT_SCHEMA",
    "get_judge",
    "parse_verdict",
    "rubrics",
    "validate",
    "validators",
]
