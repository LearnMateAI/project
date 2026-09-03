"""
Resource type 4 of 4: a summary.

    PDF passage  ->  "one block of connected prose"   (narrative, default)
                  or markdown points with **bold** leads (structured)

Narrative is the original design: connected prose, not a summary chopped into bullets.
Structured is additive. Existing stored summaries have no style field and render as
narrative.
"""

from __future__ import annotations

import re
from typing import List

from .task import Task

SUMMARY_SCHEMA = {
    "type": "object",
    "properties": {"summary": {"type": "string"}},
    "required": ["summary"],
}

DEFAULT_SENTENCES = 5
STRUCTURED_MAX_WORDS = 40

# Numbered or lettered sub-clauses that make a statute "list-like".
_CLAUSE = re.compile(
    r"(?:^|\n)\s*(?:\([0-9]+\)|\([a-z]\)|\([ivxlcdm]+\)|[0-9]+\.(?!\d)|[a-z]\.\s)",
    re.IGNORECASE,
)


def suggest_summary_style(source: str) -> str:
    """Heuristic default: structured when the passage is itself list-like."""
    if len(_CLAUSE.findall(source or "")) >= 3:
        return "structured"
    return "narrative"


def resolve_summary_style(source: str, requested: str | None) -> str:
    """User override wins; otherwise the heuristic. Unknown values fall back to narrative."""
    choice = (requested or "").strip().lower()
    if choice in ("narrative", "structured"):
        return choice
    if choice in ("auto", ""):
        return suggest_summary_style(source)
    return "narrative"


def build_prompt(source: str, count: int, style: str = "narrative") -> str:
    sentences = count or DEFAULT_SENTENCES
    if style == "structured":
        return f"""Summarise the passage below as short point-by-point statements.

PASSAGE:
\"\"\"
{source}
\"\"\"

Rules:
- Include only what the passage states. Add no outside knowledge.
- Break into points ONLY where the source is list-like (numbered subsections, enumerated
  conditions, sequential procedural steps). Do not invent subdivisions of a narrative provision.
- Start each point with the defined term or key obligation in markdown **bold**.
- Each point is one short statement (well under {STRUCTURED_MAX_WORDS} words).
- Write at least two points.
- Do not open with "This passage discusses".

Return JSON: {{"summary": "..."}}  (a single string; use markdown list lines starting with "- ")"""

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
    """Pull the string out of the summary envelope."""
    if isinstance(data, dict):
        return data.get("summary", "")
    return data if isinstance(data, str) else str(data)


def render(text) -> str:
    return text if isinstance(text, str) else str(text)


def structured_points(text: str) -> List[str]:
    """Split a structured-mode summary into points for Gate 1."""
    points: List[str] = []
    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        line = re.sub(r"^[-*]\s+", "", line)
        line = re.sub(r"^\d+[.)]\s+", "", line)
        points.append(line)
    if len(points) < 2:
        blocks = [p.strip() for p in re.split(r"\n\s*\n", text or "") if p.strip()]
        if len(blocks) > len(points):
            points = blocks
    return points


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
