"""Summary generation."""

SYSTEM_PROMPT = (
    "You summarise passages faithfully. You never state anything the passage does not "
    "support, and you never pad. Reply with JSON only."
)

SCHEMA = {
    "type": "object",
    "properties": {"summary": {"type": "string"}},
    "required": ["summary"],
}

# `count` is the task-module contract, but a summary is one artefact; it is read as a
# rough sentence budget instead of a number of items.
DEFAULT_SENTENCES = 5


def build_prompt(source: str, count: int) -> str:
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


def unwrap(data):
    if isinstance(data, dict):
        return data.get("summary", "")
    return data if isinstance(data, str) else str(data)


def render(text) -> str:
    return text if isinstance(text, str) else str(text)
