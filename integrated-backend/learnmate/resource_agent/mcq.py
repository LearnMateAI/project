"""
Resource type 1 of 4: multiple-choice questions.

    PDF passage  ->  [{question, options[4], correct_answer}, ...]

The rules in the prompt are chosen to head off exactly what the structural gate would
reject afterwards -- four options, the correct answer copied verbatim from them, no
"all of the above", no position or length giveaway. Asking for it up front is free;
catching it later costs a whole regeneration.
"""

from .task import Task, unwrap_questions

# minItems/maxItems 4 is enforced by the decoding grammar itself, so a well-formed reply
# cannot have three options. evaluator/mcq_rules.py checks it again anyway, because the
# HTTP backend may be talking to a server that ignores the schema.
MCQ_SCHEMA = {
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


DIFFICULTIES = ("easy", "medium", "hard")

_DIFFICULTY_RULES = {
    "easy": (
        "- Difficulty: EASY. Each question targets a single, explicitly-stated fact.\n"
        "- Distractors should be clearly wrong on a plain reading; one obviously "
        "implausible option is acceptable."
    ),
    "medium": (
        "- Difficulty: MEDIUM. Plausible distractors; answering requires reading the "
        "passage, not just recognising keywords."
    ),
    "hard": (
        "- Difficulty: HARD. Distractors are near-misses: a real fact from elsewhere in "
        "THIS passage, a subtly wrong number/date/section, or a commonly-confused related "
        "provision. A question may require combining two statements.\n"
        "- A hard distractor must still be factually FALSE per the source — never make "
        "the question ambiguous or arguable."
    ),
}


def resolve_difficulty(requested: str | None) -> str:
    choice = (requested or "medium").strip().lower()
    return choice if choice in DIFFICULTIES else "medium"


def build_prompt(source: str, count: int, difficulty: str = "medium") -> str:
    tier = resolve_difficulty(difficulty)
    extra = _DIFFICULTY_RULES[tier]
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
{extra}

Return JSON: {{"questions": [{{"question": "...", "options": ["...","...","...","..."], "correct_answer": "..."}}]}}"""


def render(items) -> str:
    """Flatten to the exam-paper layout the judge reads and the CLI prints."""
    lines = []
    for i, item in enumerate(items or [], start=1):
        lines.append(f"Q{i}. {item.get('question', '')}")
        for label, option in zip("ABCD", item.get("options", [])):
            lines.append(f"   {label}) {option}")
        # The answer is shown to the judge on purpose: it cannot check correctness
        # against the passage without knowing which option was marked.
        lines.append(f"   Correct: {item.get('correct_answer', '')}")
    return "\n".join(lines)


MCQ = Task(
    name="mcq",
    system_prompt=(
        "You are an expert exam writer. You write multiple-choice questions that can be "
        "answered from a given passage alone, and you never invent facts the passage does "
        "not state. Reply with JSON only."
    ),
    schema=MCQ_SCHEMA,
    build_prompt=build_prompt,
    unwrap=unwrap_questions,
    render=render,
    count_label="questions",
)
