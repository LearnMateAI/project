"""
The evaluator: two gates over generated content.

    gate 1  structural validators   plain Python, microseconds
    gate 2  an LLM rubric grade     ~25 seconds

Cheapest first. Most bad generations fail mechanically -- three options instead of four, a
correct_answer in none of them, an empty summary -- so the judge is only ever spent on
content that is already well-formed.

Two producers are graded, and they enter at different points:

    resource_agent  a generated resource (mcq, summary, keypoints, practice_qsn)
                    -> gate 1 validate(), then gate 2 judge(), against the PDF passage
    chat_agent      one chat reply
                    -> gate 2 only, via judge_chat_reply(). Free prose has no mechanical
                       structure to check, so there is no "chat_msg" validator.

Which rubric gate 2 applies is decided by the caller's *situation*, never by asking the
model: a chat reply is held to the retrieved chunks when retrieval found any, and only to
relevance and coherence when it did not.

Everything fails closed. A judge that cannot be parsed or reached returns a failing
verdict, not an exception -- the caller is mid-loop and needs a decision, and silently
passing unreviewed content through is the one outcome worth ruling out.

Where things live, in reading order:

    normalise.py    norm() -- comparison-safe text, shared by every gate-1 rule
    mcq_rules.py    gate 1 for MCQs: per-question faults and set-wide biases
    text_rules.py   gate 1 for summary, keypoints and practice questions
    validators.py   gate 1 dispatcher: validate(task, content) -> (ok, reasons)
    rubrics.py      gate 2 criteria, one per task
    prompt.py       gate 2 system prompt and message assembly
    verdict.py      gate 2 output: the schema, parsing, and the fail-closed verdicts
    judge.py        gate 2 orchestration: Judge.judge / judge_chat_reply / get_judge
"""

from . import mcq_rules, prompt, rubrics, text_rules, validators
from .judge import Judge, get_judge
from .validators import validate
from .verdict import VERDICT_SCHEMA, failed_verdict, parse_verdict, usable_instruction

__all__ = [
    "Judge",
    "VERDICT_SCHEMA",
    "failed_verdict",
    "get_judge",
    "mcq_rules",
    "parse_verdict",
    "prompt",
    "rubrics",
    "text_rules",
    "usable_instruction",
    "validate",
    "validators",
]
