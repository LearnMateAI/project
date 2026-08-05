"""
Resource type 4 of 4: a summary.

    PDF passage  ->  "one block of connected prose"

The odd one out. The other three produce a list of items and `count` means "how many";
a summary is a single artefact, so `count` is read as a rough sentence budget instead.
That is the only place the shared Task contract has to bend.
"""

from .task import Task

SUMMARY_SCHEMA = {
    "type": "object",
    "properties": {"summary": {"type": "string"}},
    "required": ["summary"],
}

# Used when the caller passes no count at all.
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
    """Pull the string out of the {"summary": "..."} envelope."""
    if isinstance(data, dict):
        return data.get("summary", "")
    return data if isinstance(data, str) else str(data)


def render(text) -> str:
    """Already plain prose; there is nothing to flatten."""
    return text if isinstance(text, str) else str(text)


SUMMARY = Task(
    name="summary",
    system_prompt=(
        "You summarise passages faithfully. You never state anything the passage does not "
        "support, and you never pad. Reply with JSON only."
    ),
    schema=SUMMARY_SCHEMA,
    build_prompt=build_prompt,
    unwrap=unwrap,
    render=render,
    count_label="sentences",
)
