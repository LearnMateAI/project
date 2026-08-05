"""
Assembling the passage a resource is generated from.

This is what a "resource" session reads. Where the chat agent retrieves a handful of
chunks per question, resource generation needs one continuous passage to write five MCQs
or a summary from -- and a whole PDF does not fit in a 4k context window, so the
interesting question is which part of it to use.

    topic given  -> the pages whose text best matches it. This is what makes
                    "5 MCQs about directors' duties" work on a 200-page book.
    pages given  -> exactly those pages
    neither      -> the opening of the document, up to the budget

The unit is always a whole page, never the retrieved chunks themselves. Chunks are sized
and overlapped for retrieval: joining them repeats ~150 characters at every boundary and
starts the passage mid-sentence, and a generator handed that writes questions about the
fragments. Retrieval picks *which* pages; the stored page text supplies the prose.
"""

from typing import List, Optional

from .. import config
from ..storage import pdf_store
from ..storage.vectors import get_vector_store


def _rank_pages_by_topic(doc_id, topic: str) -> List[int]:
    """Page numbers ordered by how well their best chunk matches the topic."""
    hits = get_vector_store().similarity_search_with_score(topic, k=12, doc_id=doc_id)

    ranked, seen = [], set()
    for document, _ in hits:
        number = document.metadata.get("page_number")
        # De-duplicated because several chunks of one page can all rank highly, and the
        # page is read whole either way.
        if number is not None and number not in seen:
            seen.add(number)
            ranked.append(number)
    return ranked


def _load_pages(doc_id, selected: Optional[List[int]]) -> List[dict]:
    """Stored page text in reading order, falling back to chunks for an older corpus."""
    records = pdf_store.get_pages(doc_id, selected)
    if records:
        return records

    # Nothing stored by store_pages: either the document predates it or only chunks
    # exist. Fall back to the chunks so an older corpus still generates.
    documents = get_vector_store().chunks_for(doc_id, pages=selected)
    return [{"page_number": d.metadata.get("page_number"), "text": d.page_content}
            for d in documents]


def _keep_most_relevant(records: List[dict], order: List[int], max_chars: int) -> List[dict]:
    """
    Trim to the budget by relevance, then restore reading order.

    Both halves matter: keeping the most relevant pages is what makes a topic query
    useful, and re-sorting them by page number is what stops the passage reading as a
    sequence of non-sequiturs.
    """
    rank = {number: position for position, number in enumerate(order)}
    records = sorted(records, key=lambda r: rank.get(r["page_number"], len(rank)))

    kept, total = [], 0
    for record in records:
        # `total and` lets the single most relevant page through even if it alone exceeds
        # the budget -- it gets truncated below rather than dropped, which beats
        # returning nothing.
        if total and total + len(record["text"]) > max_chars:
            continue
        kept.append(record)
        total += len(record["text"]) + 2

    return sorted(kept, key=lambda r: r["page_number"])


def build_source_text(doc_id, topic: str = None, pages: Optional[List[int]] = None,
                      max_chars: int = None) -> str:
    """
    The passage to generate from, as one string of whole pages in reading order.

    Raises ValueError when the document has no indexed text, which the caller surfaces as
    "ingest the PDF first" rather than generating from nothing.
    """
    max_chars = max_chars or config.MAX_SOURCE_CHARS

    selected = _rank_pages_by_topic(doc_id, topic) if topic else pages
    records = _load_pages(doc_id, selected)

    if not records:
        raise ValueError(
            f"No indexed text for document {doc_id}"
            + (f" matching {topic!r}" if topic else "")
            + ". Ingest the PDF first."
        )

    if topic:
        records = _keep_most_relevant(records, selected, max_chars)

    # Final pass: concatenate up to the budget. Pages arrive in reading order, so this
    # only ever truncates the tail.
    parts, total = [], 0
    for record in records:
        text = (record.get("text") or "").strip()
        if not text:
            continue
        if total + len(text) > max_chars:
            remaining = max_chars - total
            # Only take a partial page if enough of it fits to be worth reading.
            if remaining > 300:
                parts.append(text[:remaining])
            break
        parts.append(text)
        total += len(text) + 2

    return "\n\n".join(parts).strip()
