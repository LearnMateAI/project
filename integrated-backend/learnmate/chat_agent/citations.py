"""
Which retrieved chunks actually overlap the reply (F-09).

A citation chip is a claim of support. Listing every retrieved page made invented
section numbers look pinned. Keep a chip only when the reply and the chunk share
enough content words.
"""

import re
from typing import Any, Dict, List

_WORD = re.compile(r"[a-z0-9]{3,}")


def _words(text: str) -> set:
    return set(_WORD.findall((text or "").lower()))


def overlapping_citations(reply: str, contexts, min_overlap: int = 3) -> List[Dict[str, Any]]:
    """Citations whose chunk text overlaps the reply enough to be honest pin-cites."""
    reply_words = _words(reply)
    cites = []
    for doc in contexts or []:
        meta = getattr(doc, "metadata", None) or {}
        chunk_words = _words(getattr(doc, "page_content", "") or "")
        if len(reply_words & chunk_words) < min_overlap:
            continue
        cites.append({
            "page": meta.get("page_number"),
            "paragraph": (
                meta.get("chunk_index") + 1
                if isinstance(meta.get("chunk_index"), int)
                else None
            ),
        })
    return cites
