"""
Gate 1 for multiple-choice questions.

By far the largest structural check, because an MCQ set can be broken in two different
ways:

    per question   three options instead of four, a correct_answer matching none of them,
                   duplicate or blank options, an "all of the above" giveaway
    per set        biases only visible across questions -- the answer always in slot B,
                   the correct option always the longest, the same question asked twice

The set-level rules are the interesting ones. Each question can be individually perfect
while the set as a whole is still guessable without reading the passage, and no
single-item check can see that.

Every checker returns (ok, reasons). `reasons` is phrased as faults so it can be handed
straight to the generator as a regeneration instruction when the LLM judge never runs.
"""

import re
from typing import List, Tuple

from .normalise import norm

# A distractor that gives the answer away by referring to the other options.
_META_OPTION = re.compile(r"\b(all|none|both)\s+of\s+the\s+(above|these|following)\b",
                          re.IGNORECASE)

# Below this many questions, a "bias" is just a coincidence: with three questions the
# answer landing in the same slot each time happens by chance often enough to be useless
# as a signal.
_MIN_FOR_BIAS = 4


def validate_mcq(item: dict) -> Tuple[bool, List[str]]:
    """Check one multiple-choice question."""
    reasons = []

    question = str(item.get("question", "")).strip()
    options = item.get("options") or []
    correct = item.get("correct_answer", "")

    if not question:
        reasons.append("a question has empty question text")

    if not isinstance(options, list) or len(options) != 4:
        count = len(options) if isinstance(options, list) else 0
        reasons.append(f"question {question[:40]!r} has {count} options instead of exactly 4")
        # Without four options the remaining checks would report noise.
        return (not reasons), reasons

    normalised = [norm(option) for option in options]

    if any(not option for option in normalised):
        reasons.append(f"question {question[:40]!r} has a blank option")
    if len(set(normalised)) != len(normalised):
        reasons.append(f"question {question[:40]!r} has duplicate options")
    if norm(correct) not in normalised:
        reasons.append(f"question {question[:40]!r} has a correct_answer that is not one "
                       "of its options")
    if any(_META_OPTION.search(str(option)) for option in options):
        reasons.append(f"question {question[:40]!r} uses an 'all/none of the above' option")

    return (not reasons), reasons


def _answer_positions(items) -> List[int]:
    """Which slot the correct answer sits in, per question that has a findable answer."""
    positions = []
    for item in items:
        options = [norm(option) for option in (item.get("options") or [])]
        correct = norm(item.get("correct_answer", ""))
        if correct in options:
            positions.append(options.index(correct))
    return positions


def _correct_is_longest(items) -> List[bool]:
    """Per question, whether the correct option is also the longest one."""
    flags = []
    for item in items:
        options = [str(option) for option in (item.get("options") or [])]
        correct = norm(item.get("correct_answer", ""))
        if len(options) == 4 and correct:
            flags.append(norm(max(options, key=len)) == correct)
    return flags


def validate_mcq_set(items) -> Tuple[bool, List[str]]:
    """Check a whole MCQ set, including biases only visible across questions."""
    if not items:
        return False, ["no questions were generated"]

    reasons = []
    for item in items:
        _, item_reasons = validate_mcq(item)
        reasons.extend(item_reasons)

    # Position bias: a set where the answer is always in the same slot is guessable
    # without reading the question at all.
    positions = _answer_positions(items)
    if len(positions) >= _MIN_FOR_BIAS and len(set(positions)) == 1:
        reasons.append(f"the correct answer is in position {positions[0] + 1} for every question")

    # Length bias: if the correct option is always the longest, length alone gives it away.
    longest = _correct_is_longest(items)
    if len(longest) >= _MIN_FOR_BIAS and all(longest):
        reasons.append("the correct answer is the longest option in every question")

    # The same fact asked twice with different wording still halves the value of the set.
    stems = [norm(item.get("question", "")) for item in items]
    if len(set(stems)) != len(stems):
        reasons.append("two questions are identical")

    return (not reasons), reasons
