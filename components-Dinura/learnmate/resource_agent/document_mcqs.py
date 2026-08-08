"""
Multiple-choice questions over a whole document.

The count-based entry point onto whole_document.generate_document_items, kept separate
because "how many questions do you want" is the question a caller actually has, and
because the counts the CLI offers belong next to the task they size.

    generate_document_mcqs(doc_id, count=40)

Forty is not something `generate_resource` can deliver: one reply holds about eight MCQs
before it is cut off, and one passage is 6000 characters of the opening pages. See
whole_document.py for how the document is split and the results pooled.
"""

from typing import Dict

from .whole_document import generate_document_items

# What the CLI offers. Not a limit: any count can be passed directly.
COUNT_CHOICES = (10, 20, 40)
DEFAULT_COUNT = 20


def generate_document_mcqs(doc_id, count: int = DEFAULT_COUNT, threshold: int = None,
                           max_attempts: int = None, evaluate: bool = True,
                           persist: bool = True, verbose: bool = True,
                           max_chars: int = None) -> Dict:
    """
    Write `count` multiple-choice questions drawn from across the whole document.

    A thin alias for generate_document_items(task="mcq", count=...); see that function for
    what comes back and how the count is spread.
    """
    return generate_document_items(
        "mcq", doc_id, count=count, threshold=threshold, max_attempts=max_attempts,
        evaluate=evaluate, persist=persist, verbose=verbose, max_chars=max_chars)
