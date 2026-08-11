"""
Resource type 2 of 4: short-answer practice questions.

    PDF passage  ->  [{question, answer}, ...]

The same {"questions": [...]} envelope as mcq -- hence the shared `unwrap_questions` --
but each item carries a written answer instead of four options. Where an MCQ tests
recognition, these test recall, so the prompt pushes for questions whose answers are
stated in the passage without being a single word lifted from it.
"""

from .task import Task, unwrap_questions

PRACTICE_SCHEMA = {
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


def render(items) -> str:
    """Numbered Q/A pairs -- the same shape as mcq, so neither collides with the rubric."""
    lines = []
    for i, item in enumerate(items or [], start=1):
        lines.append(f"Q{i}. {item.get('question', '')}")
        lines.append(f"   A: {item.get('answer', '')}")
    return "\n".join(lines)


PRACTICE_QSN = Task(
    name="practice_qsn",
    system_prompt=(
        "You are an expert exam writer. You write short-answer practice questions whose "
        "answers appear in the given passage, and you never invent facts the passage does "
        "not state. Reply with JSON only."
    ),
    schema=PRACTICE_SCHEMA,
    build_prompt=build_prompt,
    unwrap=unwrap_questions,
    render=render,
    count_label="questions",
)
