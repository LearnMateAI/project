"""
Cheap input refusals before a 30–60s chat job is queued (F-07).

Not a full safety model. Legal course text may mention crime; we only block
clear self-harm, weapons how-to, and exam-theft asks.
"""

import re

_BLOCK = (
    (re.compile(r"\b(kill myself|suicide method|end my life)\b", re.I),
     "I cannot help with that. If you are in crisis, contact local emergency services."),
    (re.compile(r"\bhow to (make|build) (a )?(bomb|explosive|weapon)\b", re.I),
     "I cannot help with weapons or explosives."),
    (re.compile(r"\b(scrape|download|steal)\b.{0,40}\bexam( papers| questions)?\b", re.I),
     "I cannot help steal or scrape exam papers. Ask about the uploaded document instead."),
)


def refuse_reason(message: str) -> str | None:
    """Why this message must not be queued, or None to allow it."""
    text = (message or "").strip()
    if not text:
        return None
    for pattern, reason in _BLOCK:
        if pattern.search(text):
            return reason
    return None
