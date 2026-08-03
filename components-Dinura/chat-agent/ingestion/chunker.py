"""
Splits cleaned page text into sub-page chunks before embedding.

Embedding a whole page as one vector makes retrieval coarse: a page holding six articles
produces one averaged vector, so the specific article a question asks about is diluted by
everything else on the page. Worse, a keyword-dense contents page out-scores the article
text itself, because a list of every chapter title matches almost any topical query.

Chunking on sentence boundaries gives each passage its own vector, so a focused article
competes on its own terms.

TextPreprocessor flattens newlines into spaces, so there are no paragraph breaks left to
split on by the time text reaches here -- sentence boundaries are all we have. Legal prose
also breaks at ';' and at numbered clauses like '(2)', so both count as boundaries.
"""

import re

# Sentence-ish boundary: after . ; : ? ! followed by whitespace, or before a numbered
# clause marker such as "(2)" / "(iii)" that starts a new provision.
_BOUNDARY = re.compile(r"(?<=[.;:?!])\s+|\s+(?=\(\s*(?:\d{1,3}|[ivxlcdm]{1,7})\s*\))", re.IGNORECASE)

DEFAULT_CHUNK_CHARS = 900
DEFAULT_OVERLAP_CHARS = 150
DEFAULT_MIN_CHARS = 80


def split_sentences(text: str) -> list[str]:
    """Break flattened page text into sentence-like units, dropping empties."""
    return [part.strip() for part in _BOUNDARY.split(text or "") if part and part.strip()]


def _pack(sentences: list[str], chunk_chars: int, overlap_chars: int) -> list[str]:
    """
    Greedily fill chunks up to chunk_chars, carrying the tail of each chunk into the next.

    The overlap keeps a provision that straddles a boundary retrievable from either side.
    """
    chunks, current, size = [], [], 0

    for sentence in sentences:
        # A single sentence longer than the budget becomes its own chunk rather than being
        # cut mid-clause; legal sentences are long and splitting them loses the subject.
        if size and size + len(sentence) + 1 > chunk_chars:
            chunks.append(" ".join(current))

            tail, tail_size = [], 0
            for prev in reversed(current):
                if tail_size + len(prev) > overlap_chars:
                    break
                tail.insert(0, prev)
                tail_size += len(prev) + 1
            current, size = tail, tail_size

        current.append(sentence)
        size += len(sentence) + 1

    if current:
        chunks.append(" ".join(current))
    return chunks


def _is_substantive(text: str, min_chars: int) -> bool:
    """Reject running heads and title pages: short strings with little alphanumeric content."""
    return len(re.sub(r"[^A-Za-z0-9]", "", text)) >= min_chars


def chunk_pages(pages: list[dict], chunk_chars: int = DEFAULT_CHUNK_CHARS,
                overlap_chars: int = DEFAULT_OVERLAP_CHARS,
                min_chars: int = DEFAULT_MIN_CHARS) -> list[dict]:
    """
    Turn TextPreprocessor output into embeddable chunks.

    pages  -- [{page_index, page_number, page_content}, ...]
    returns   [{page_index, page_number, chunk_index, text}, ...]

    `chunk_index` is per page and, with the source path, gives each chunk a stable identity
    so re-ingesting a document overwrites its chunks instead of duplicating them.
    """
    out = []
    for page in pages:
        content = (page.get("page_content") or "").strip()
        if not content:
            continue

        for i, text in enumerate(_pack(split_sentences(content), chunk_chars, overlap_chars)):
            if not _is_substantive(text, min_chars):
                continue
            out.append({
                "page_index": page["page_index"],
                "page_number": page["page_number"],
                "chunk_index": i,
                "text": text,
            })
    return out
