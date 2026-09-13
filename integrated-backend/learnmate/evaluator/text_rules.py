"""
Gate 1 for the three prose resource types.

Short by design. There is little structure to check in a summary or a key point, so these
only catch the failures that need no judgement at all -- empty, too thin to be worth
reading, or duplicated. Everything else about them is a quality question, which is gate
2's job.

    practice_qsn  question and answer both present, the answer not a restatement
    keypoints     enough points, none empty, none duplicated
    summary       present, and long enough to have covered anything

Every checker returns (ok, reasons), phrased as faults so it can be handed straight to the
generator when the LLM judge never runs.
"""

from typing import List, Tuple

from .normalise import norm


def validate_practice_qsn(items) -> Tuple[bool, List[str]]:
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
        elif norm(answer) == norm(question):
            # A model padding out a set will echo the question back as its own answer.
            reasons.append(f"question {question[:40]!r} has an answer that just restates "
                           "the question")
    return (not reasons), reasons


def validate_keypoints(items, min_points: int = 2) -> Tuple[bool, List[str]]:
    """Check extracted key points."""
    if not items:
        return False, ["no key points were generated"]

    reasons = []
    points = [str(point).strip() for point in items]

    if len(points) < min_points:
        reasons.append(f"only {len(points)} key point(s) were produced, fewer than {min_points}")
    if any(not point for point in points):
        reasons.append("a key point is empty")
    if len({norm(point) for point in points}) != len(points):
        reasons.append("two key points are duplicates of each other")
    return (not reasons), reasons


def validate_summary(text, min_chars: int = 80, style: str = "narrative") -> Tuple[bool, List[str]]:
    """
    Check a summary.

    Narrative (default): only length — a summary shorter than a sentence or two cannot
    have covered a page of source. Faithfulness is gate 2.

    Structured: at least two points, none empty, none over ~40 words (paragraph stuffed
    into a bullet).
    """
    text = str(text or "").strip()
    reasons = []

    if not text:
        reasons.append("the summary is empty")
        return False, reasons

    if (style or "narrative") == "structured":
        from learnmate.resource_agent.summary import STRUCTURED_MAX_WORDS, structured_points

        points = structured_points(text)
        if len(points) < 2:
            reasons.append("a structured summary must contain at least two points")
        for point in points:
            words = len(point.split())
            if words > STRUCTURED_MAX_WORDS:
                reasons.append(
                    f"a structured point is {words} words, over {STRUCTURED_MAX_WORDS} "
                    "(it reads as a paragraph in bullet clothing)"
                )
        return (not reasons), reasons

    if len(text) < min_chars:
        reasons.append(f"the summary is only {len(text)} characters, too short to cover "
                       "the source")
    return (not reasons), reasons
