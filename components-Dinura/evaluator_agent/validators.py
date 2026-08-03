"""
Deterministic structural checks, run before the LLM judge.

Most bad generations fail mechanically rather than qualitatively: three options instead of
four, a correct_answer that appears in no option, duplicate distractors, an empty answer.
Those are decidable in plain Python in microseconds, and catching them here means the
~25 second judge call is only ever spent on content that is already well-formed.

Every checker returns (ok, reasons). `reasons` is phrased as faults so it can be handed
straight to the generator as a regeneration instruction when the LLM judge never runs.
"""

import re

# A distractor that gives the answer away by referring to the other options.
_META_OPTION = re.compile(r"\b(all|none|both)\s+of\s+the\s+(above|these|following)\b", re.IGNORECASE)


def _norm(text) -> str:
    """Compare text without being fooled by spacing, case or trailing punctuation."""
    return re.sub(r"\s+", " ", str(text or "")).strip().strip(".?!,;:").lower()


def validate_mcq(item: dict) -> tuple:
    """Check one multiple-choice question."""
    reasons = []

    question = str(item.get("question", "")).strip()
    options = item.get("options") or []
    correct = item.get("correct_answer", "")

    if not question:
        reasons.append("a question has empty question text")
    if not isinstance(options, list) or len(options) != 4:
        reasons.append(f"question {question[:40]!r} has {len(options) if isinstance(options, list) else 0} "
                       "options instead of exactly 4")
        # Without four options the remaining checks would report noise.
        return (not reasons), reasons

    normalised = [_norm(o) for o in options]

    if any(not o for o in normalised):
        reasons.append(f"question {question[:40]!r} has a blank option")
    if len(set(normalised)) != len(normalised):
        reasons.append(f"question {question[:40]!r} has duplicate options")
    if _norm(correct) not in normalised:
        reasons.append(f"question {question[:40]!r} has a correct_answer that is not one of its options")
    if any(_META_OPTION.search(str(o)) for o in options):
        reasons.append(f"question {question[:40]!r} uses an 'all/none of the above' option")

    return (not reasons), reasons


def validate_mcq_set(items) -> tuple:
    """Check a whole MCQ set, including biases only visible across questions."""
    if not items:
        return False, ["no questions were generated"]

    reasons = []
    for item in items:
        _, item_reasons = validate_mcq(item)
        reasons.extend(item_reasons)

    # Position bias: a set where the answer is always in the same slot is guessable
    # without reading the question. Only meaningful once there are a few questions.
    positions = []
    for item in items:
        options = [_norm(o) for o in (item.get("options") or [])]
        correct = _norm(item.get("correct_answer", ""))
        if correct in options:
            positions.append(options.index(correct))
    if len(positions) >= 4 and len(set(positions)) == 1:
        reasons.append(f"the correct answer is in position {positions[0] + 1} for every question")

    # Length bias: if the correct option is always the longest, length alone gives it away.
    longest = []
    for item in items:
        options = [str(o) for o in (item.get("options") or [])]
        correct = _norm(item.get("correct_answer", ""))
        if len(options) == 4 and correct:
            longest.append(_norm(max(options, key=len)) == correct)
    if len(longest) >= 4 and all(longest):
        reasons.append("the correct answer is the longest option in every question")

    return (not reasons), reasons


def validate_practice_qsn(items) -> tuple:
    """Check short-answer questions."""
    if not items:
        return False, ["no questions were generated"]

    reasons = []
    for item in items:
        question = str(item.get("question", "")).strip()
        answer = str(item.get("answer", "")).strip()
        if not question:
            reasons.append("a question has empty question text")
        if not answer:
            reasons.append(f"question {question[:40]!r} has an empty answer")
        elif _norm(answer) == _norm(question):
            reasons.append(f"question {question[:40]!r} has an answer that just restates the question")
    return (not reasons), reasons


def validate_keypoints(items, min_points: int = 2) -> tuple:
    """Check extracted key points."""
    if not items:
        return False, ["no key points were generated"]

    reasons = []
    points = [str(p).strip() for p in items]

    if len(points) < min_points:
        reasons.append(f"only {len(points)} key point(s) were produced, fewer than {min_points}")
    if any(not p for p in points):
        reasons.append("a key point is empty")
    if len({_norm(p) for p in points}) != len(points):
        reasons.append("two key points are duplicates of each other")
    return (not reasons), reasons


def validate_summary(text, min_chars: int = 80) -> tuple:
    """Check a summary."""
    text = str(text or "").strip()
    reasons = []
    if not text:
        reasons.append("the summary is empty")
    elif len(text) < min_chars:
        reasons.append(f"the summary is only {len(text)} characters, too short to cover the source")
    return (not reasons), reasons


# task name -> the checker the orchestrator should run before calling the judge
VALIDATORS = {
    "mcq": validate_mcq_set,
    "practice_qsn": validate_practice_qsn,
    "keypoints": validate_keypoints,
    "summary": validate_summary,
}


def validate(task: str, content) -> tuple:
    """Run the checker for `task`; unknown tasks pass through so the judge still sees them."""
    checker = VALIDATORS.get(task)
    if checker is None:
        return True, []
    return checker(content)
