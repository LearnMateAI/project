"""
The four kinds of study resource, one Task each.

A Task owns everything type-specific: the system prompt, the user prompt builder, the JSON
schema that constrains decoding, how to unwrap the parsed reply, and how to flatten the
result into the text the judge grades. Everything else -- the model, the retry contract,
persistence -- is shared, so adding a fifth kind of resource means adding a Task and
nothing else.

Every schema is wrapped in an object rather than returned as a bare array: llama.cpp's
grammar support is more reliable for a top-level object, and `unwrap` hides the difference.
"""

from dataclasses import dataclass
from typing import Any, Callable, Dict, List


@dataclass(frozen=True)
class Task:
    name: str
    system_prompt: str
    schema: Dict[str, Any]
    build_prompt: Callable[[str, int], str]
    unwrap: Callable[[Any], Any]
    render: Callable[[Any], str]
    # What `count` means when the CLI asks for it, shown in help text.
    count_label: str = "items"


# --- Multiple-choice questions -------------------------------------------------------

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


def _mcq_prompt(source: str, count: int) -> str:
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


def _mcq_unwrap(data):
    if isinstance(data, dict):
        return data.get("questions", [])
    return data if isinstance(data, list) else []


def _mcq_render(items) -> str:
    lines = []
    for i, item in enumerate(items or [], start=1):
        lines.append(f"Q{i}. {item.get('question', '')}")
        for label, option in zip("ABCD", item.get("options", [])):
            lines.append(f"   {label}) {option}")
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
    build_prompt=_mcq_prompt,
    unwrap=_mcq_unwrap,
    render=_mcq_render,
    count_label="questions",
)


# --- Short-answer practice questions -------------------------------------------------

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


def _practice_prompt(source: str, count: int) -> str:
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


def _practice_render(items) -> str:
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
    build_prompt=_practice_prompt,
    unwrap=_mcq_unwrap,  # same {"questions": [...]} envelope
    render=_practice_render,
    count_label="questions",
)


# --- Key points ----------------------------------------------------------------------

KEYPOINTS_SCHEMA = {
    "type": "object",
    "properties": {"keypoints": {"type": "array", "items": {"type": "string"}}},
    "required": ["keypoints"],
}


def _keypoints_prompt(source: str, count: int) -> str:
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


def _keypoints_unwrap(data):
    if isinstance(data, dict):
        return data.get("keypoints", [])
    return data if isinstance(data, list) else []


def _keypoints_render(items) -> str:
    return "\n".join(f"- {point}" for point in (items or []))


KEYPOINTS = Task(
    name="keypoints",
    system_prompt=(
        "You extract the key points of a passage. Every point you write must be supported "
        "by the passage; you never add outside knowledge. Reply with JSON only."
    ),
    schema=KEYPOINTS_SCHEMA,
    build_prompt=_keypoints_prompt,
    unwrap=_keypoints_unwrap,
    render=_keypoints_render,
    count_label="points",
)


# --- Summary -------------------------------------------------------------------------

SUMMARY_SCHEMA = {
    "type": "object",
    "properties": {"summary": {"type": "string"}},
    "required": ["summary"],
}

# `count` is the shared Task contract, but a summary is one artefact; it is read as a
# rough sentence budget instead of a number of items.
DEFAULT_SENTENCES = 5


def _summary_prompt(source: str, count: int) -> str:
    sentences = count or DEFAULT_SENTENCES
    return f"""Summarise the passage below in about {sentences} sentences.

PASSAGE:
\"\"\"
{source}
\"\"\"

Rules:
- Include only what the passage states. Add no outside knowledge and no interpretation.
- Cover the main points rather than only the opening ones.
- Write plain connected prose, not a bulleted list.
- Do not open with a phrase like "This passage discusses"; state the content directly.

Return JSON: {{"summary": "..."}}"""


def _summary_unwrap(data):
    if isinstance(data, dict):
        return data.get("summary", "")
    return data if isinstance(data, str) else str(data)


def _summary_render(text) -> str:
    return text if isinstance(text, str) else str(text)


SUMMARY = Task(
    name="summary",
    system_prompt=(
        "You summarise passages faithfully. You never state anything the passage does not "
        "support, and you never pad. Reply with JSON only."
    ),
    schema=SUMMARY_SCHEMA,
    build_prompt=_summary_prompt,
    unwrap=_summary_unwrap,
    render=_summary_render,
    count_label="sentences",
)


TASKS: Dict[str, Task] = {
    "mcq": MCQ,
    "practice_qsn": PRACTICE_QSN,
    "keypoints": KEYPOINTS,
    "summary": SUMMARY,
}

TASK_NAMES: List[str] = sorted(TASKS)


def get_task(name: str) -> Task:
    task = TASKS.get(name)
    if task is None:
        raise ValueError(f"Unknown task {name!r}; expected one of {TASK_NAMES}")
    return task


def render(task_name: str, content) -> str:
    """Flatten generated content into the plain text the judge grades."""
    task = TASKS.get(task_name)
    return task.render(content) if task else str(content)
