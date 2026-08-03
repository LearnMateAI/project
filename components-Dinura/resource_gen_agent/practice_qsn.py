"""Short-answer practice question generation."""

SYSTEM_PROMPT = (
    "You are an expert exam writer. You write short-answer practice questions whose "
    "answers appear in the given passage, and you never invent facts the passage does "
    "not state. Reply with JSON only."
)

SCHEMA = {
    "type": "object",
    "properties": {
        "questions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "question": {"type": "string"},
                    "answer": {"type": "string"},
                },
                "required": ["question", "answer"],
            },
        }
    },
    "required": ["questions"],
}


def build_prompt(source: str, count: int) -> str:
    return f"""Write {count} short-answer practice questions based only on the passage below.

PASSAGE:
\"\"\"
{source}
\"\"\"

Rules:
- Each answer must be stated in, or directly inferable from, the passage.
- Answers are one or two sentences, not essays.
- Do not ask a question whose answer merely restates the question.
- Vary what the questions test: definitions, conditions, exceptions, consequences.

Return JSON: {{"questions": [{{"question": "...", "answer": "..."}}]}}"""


def unwrap(data):
    if isinstance(data, dict):
        return data.get("questions", [])
    return data if isinstance(data, list) else []


def render(items) -> str:
    lines = []
    for i, item in enumerate(items or [], start=1):
        lines.append(f"Q{i}. {item.get('question', '')}")
        lines.append(f"   A: {item.get('answer', '')}")
    return "\n".join(lines)
