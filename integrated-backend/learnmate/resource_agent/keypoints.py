"""
Resource type 3 of 4: key points.

    PDF passage  ->  ["point", "point", ...]

The only task whose content is a bare list of strings, which is also why it is the only
one whose rendering had to be fixed -- see the note on `render` below.
"""

from .task import Task

KEYPOINTS_SCHEMA = {
    "type": "object",
    "properties": {"keypoints": {"type": "array", "items": {"type": "string"}}},
    "required": ["keypoints"],
}


def build_prompt(source: str, count: int) -> str:
    return f"""Extract the {count} most important key points from the passage below.

PASSAGE:
\"\"\"
{source}
\"\"\"

Rules:
- Every point must be supported by the passage. Add nothing from outside it.
- Each point is one self-contained sentence that makes sense on its own.
- Points must not repeat or paraphrase each other.
- Prefer what the passage treats as significant over incidental detail.

Return JSON: {{"keypoints": ["...", "..."]}}"""


def unwrap(data):
    """Pull the list out of the {"keypoints": [...]} envelope, or accept a bare list."""
    if isinstance(data, dict):
        return data.get("keypoints", [])
    return data if isinstance(data, list) else []


def render(items) -> str:
    """
    Numbered, not bulleted -- and that is load-bearing, not cosmetic.

    The judge's prompt puts the rubric and the content in the same message, and every
    rubric in evaluator/rubrics.py is a "- " bulleted list. Rendering key points with "- "
    too made the two read as one list: the judge counted the five rubric criteria as
    points 1-5 and the real key points as 6-10, then rejected a perfectly grounded set for
    "invented points (4, 5, 6, 7, 8)" -- items 4-5 being its own criteria.

    Numbering makes the content unmistakably a separate list, which is why the other
    list-shaped tasks never showed the fault: mcq and practice_qsn already render as
    "Q1.", "Q2.".
    """
    return "\n".join(f"{i}. {point}"
                     for i, point in enumerate(items or [], start=1))


KEYPOINTS = Task(
    name="keypoints",
    system_prompt=(
        "You extract the key points of a passage. Every point you write must be supported "
        "by the passage; you never add outside knowledge. Reply with JSON only."
    ),
    schema=KEYPOINTS_SCHEMA,
    build_prompt=build_prompt,
    unwrap=unwrap,
    render=render,
    count_label="points",
)
