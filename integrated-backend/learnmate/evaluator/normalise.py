"""
Comparison-safe text, shared by every structural check.

Almost every rule in gate 1 is a comparison: is the correct answer one of the options,
are two key points duplicates, does an answer merely restate its question. A generator
that writes "The Cabinet." in one place and "the cabinet" in another means the same
thing, and a check that says otherwise reports a fault that is not there.
"""

import re


def norm(text) -> str:
    """
    Collapse whitespace, strip trailing punctuation, lowercase.

    Applied to both sides of every comparison, so the checks are about content rather
    than about how the model happened to punctuate.
    """
    return re.sub(r"\s+", " ", str(text or "")).strip().strip(".?!,;:").lower()
