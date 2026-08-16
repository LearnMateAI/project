"""
The shape of a verdict, and how a model reply becomes one.

    {task, score, passed, reasoning, regeneration_instruction, threshold}

Everything here fails closed. A judge that cannot be parsed, cannot be reached, or answers
with something unusable produces a *failing* verdict rather than an exception -- the caller
is mid-loop and needs a decision, and silently passing unreviewed content through is the
one outcome worth ruling out. The reason always travels in `reasoning`, so a failure stays
visible instead of looking like a bad score.
"""

import re
from typing import Any, Dict

from ..llm import parse_json_reply

# Constrained decoding: llama.cpp compiles this into a grammar, so the model cannot emit
# prose around the JSON or invent extra keys.
VERDICT_SCHEMA = {
    "type": "object",
    "properties": {
        "score": {"type": "integer", "minimum": 1, "maximum": 100},
        "reasoning": {"type": "string"},
        "regeneration_instruction": {"type": "string"},
    },
    "required": ["score", "reasoning", "regeneration_instruction"],
}

# A bare verb, optionally trailing dots: the judge echoing the prompt's example rather
# than writing an order. Anything this matches carries no information for the generator.
_BARE_VERB = re.compile(r"^(remove|rewrite|add|replace|revise|correct|fix)?[\s.…]*$",
                        re.IGNORECASE)

# Shorter than this and an "instruction" cannot name both a fault and a correction.
_MIN_INSTRUCTION_CHARS = 20


def usable_instruction(instruction: str, reasoning: str) -> str:
    """
    Guarantee the retry loop has something to act on.

    A 3B judge intermittently answers with the example verb from the system prompt
    ("Rewrite...") instead of an actual order. Regenerating on that is strictly worse than
    not regenerating: the generator gets no signal and tends to collapse into a vaguer
    answer. The reasoning field does describe the fault, so fall back to it.
    """
    instruction = (instruction or "").strip()
    if len(instruction) >= _MIN_INSTRUCTION_CHARS and not _BARE_VERB.match(instruction):
        return instruction

    reasoning = (reasoning or "").strip()
    if reasoning:
        return f"Fix exactly this problem and change nothing else: {reasoning}"
    return "Regenerate the content; the evaluator returned no usable instruction."


def failed_verdict(task: str, threshold: int, reasoning: str, instruction: str) -> Dict:
    """A complete, failing verdict for when the judge could not produce one itself."""
    return {
        "task": task,
        "score": 1,
        "passed": False,
        "reasoning": reasoning,
        "regeneration_instruction": instruction,
        "threshold": threshold,
    }


def gated_verdict(task: str, threshold: int, reasoning: str) -> Dict:
    """
    A complete, passing verdict for content the judge was deliberately not asked about.

    The mirror of `failed_verdict`: same shape, opposite direction, and neither of them
    came from a model. `score` is **None** rather than a flattering number, which is the
    whole point -- a turn nobody graded must not be able to masquerade as one that scored
    well. Callers that rank attempts skip it (persist._score_of wants an int), analytics
    that average scores exclude it (evaluation_stats matches on a numeric score), and a UI
    that shows "Reviewed 92/100" shows nothing at all.

    `passed` is True because the turn is accepted and delivered; `gated` is what
    distinguishes that from having earned a pass. See chat_agent/gate.py for when this
    applies.
    """
    return {
        "task": task,
        "score": None,
        "passed": True,
        "reasoning": reasoning,
        # Empty like any passing verdict: there is nothing for the generator to fix, and
        # decide() must not be handed an instruction that would start a retry.
        "regeneration_instruction": "",
        "threshold": threshold,
        "gated": True,
    }


def parse_verdict(raw: Any) -> Dict:
    """
    Turn the model's reply into a verdict dict, tolerating stray prose or code fences.

    Returns only {score, reasoning, regeneration_instruction}; the Judge adds task,
    threshold and passed. Every failure path yields score 1 rather than raising.
    """
    try:
        data = parse_json_reply(raw)
    except ValueError:
        data = None

    if not isinstance(data, dict):
        # Unparseable, or valid JSON of the wrong shape (a list, a bare string).
        text = raw if isinstance(raw, str) else str(raw)
        return {
            "score": 1,
            "reasoning": f"Could not parse evaluator output: {text.strip()[:200]}",
            "regeneration_instruction": "Regenerate the content; the evaluator returned "
                                        "an unreadable verdict.",
        }

    try:
        # float() first so "85" and 85.0 both survive; a model ignoring the integer
        # constraint should not cost a verdict.
        score = int(float(data.get("score", 1)))
    except (TypeError, ValueError):
        score = 1

    reasoning = str(data.get("reasoning", "")).strip()

    return {
        # Clamped: a schema-free backend can return 0 or 120, and a score outside the
        # range would make every threshold comparison meaningless.
        "score": max(1, min(100, score)),
        "reasoning": reasoning,
        "regeneration_instruction": usable_instruction(
            str(data.get("regeneration_instruction", "")), reasoning),
    }
