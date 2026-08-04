"""Key-point extraction."""

SYSTEM_PROMPT = (
    "You extract the key points of a passage. Every point you write must be supported by "
    "the passage; you never add outside knowledge. Reply with JSON only."
)

SCHEMA = {
    "type": "object",
    "properties": {
        "keypoints": {"type": "array", "items": {"type": "string"}},
    },
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
    if isinstance(data, dict):
        return data.get("keypoints", [])
    return data if isinstance(data, list) else []


def render(items) -> str:
    return "\n".join(f"- {point}" for point in (items or []))
