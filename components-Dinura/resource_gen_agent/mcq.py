"""Multiple-choice question generation."""

SYSTEM_PROMPT = (
    "You are an expert exam writer. You write multiple-choice questions that can be "
    "answered from a given passage alone, and you never invent facts the passage does "
    "not state. Reply with JSON only."
)

# Wrapped in an object rather than returned as a bare array: llama.cpp's grammar support is
# more reliable for a top-level object, and unwrap() hides the difference from callers.
SCHEMA = {
    "type": "object",
    "properties": {
        "questions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "question": {"type": "string"},
                    "options": {
                        "type": "array",
                        "items": {"type": "string"},
                        "minItems": 4,
                        "maxItems": 4,
                    },
                    "correct_answer": {"type": "string"},
                },
                "required": ["question", "options", "correct_answer"],
            },
        }
    },
    "required": ["questions"],
}


def build_prompt(source: str, count: int) -> str:
    return f"""Write {count} multiple-choice questions based only on the passage below.

PASSAGE:
\"\"\"
{source}
\"\"\"

Rules:
- Every question must be answerable from the passage alone.
- Exactly four options per question.
- "correct_answer" must be copied verbatim from that question's own options.
- The three wrong options must be plausible but clearly wrong according to the passage.
- Do not make the correct option consistently the longest, and do not always put it first.
- Never use "All of the above" or "None of the above".

Return JSON: {{"questions": [{{"question": "...", "options": ["...","...","...","..."], "correct_answer": "..."}}]}}"""


def unwrap(data):
    """Accept the wrapped object or a bare array, since the fallback path is unconstrained."""
    if isinstance(data, dict):
        return data.get("questions", [])
    return data if isinstance(data, list) else []


def render(items) -> str:
    """Flatten to the text the evaluator grades."""
    lines = []
    for i, item in enumerate(items or [], start=1):
        lines.append(f"Q{i}. {item.get('question', '')}")
        for label, option in zip("ABCD", item.get("options", [])):
            lines.append(f"   {label}) {option}")
        lines.append(f"   Correct: {item.get('correct_answer', '')}")
    return "\n".join(lines)
