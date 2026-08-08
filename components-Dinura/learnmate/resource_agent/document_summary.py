"""
A summary of a whole document, not just the passage that fits the context window.

`generate_resource("summary", source)` can only see what `build_source_text` handed it --
MAX_SOURCE_CHARS of the opening pages -- so on anything longer the tail of the PDF is
never read. This walks every stored page instead and folds the results:

    page 1 ---> summary 1 --+
    page 2 ---> summary 2 --+--> one paragraph for the document
    ...                     |
    page n ---> summary n --+

Two passes, for two different reasons. The per-page pass is what makes the whole document
readable at all: each page fits the window on its own. The fold is what turns n paragraphs
back into one, and it repeats while the page summaries together still overrun the budget,
so a 200-page book reduces in rounds rather than being truncated.

Only the final round goes through the graph, so the judge grades the paragraph the caller
actually gets -- against the page summaries it was written from, which is the source it was
in fact asked to be faithful to. The per-page pass skips evaluation by default: judging
every page costs ~25 seconds each and buys nothing the final gate does not already check.
"""

from typing import Dict, List

from .. import config
from ..storage import pdf_store
from .agent import generate_resource
from .helpers import _log
# The page filter and the grouping are shared with the pooled tasks. The page *loading* is
# not: a summary reports which page each note came from, so it needs the records whole.
from .whole_document import MIN_PAGE_CHARS, batched

# Sentences asked of a single page. Deliberately tight: these are intermediate notes to be
# folded, and a verbose per-page pass just crowds the fold's own budget.
PAGE_SENTENCES = 2

# --- How long the final summary is allowed to be ---------------------------------------
# Scaled to the document rather than fixed: five sentences is a fair summary of a page and
# a useless one of eighty, so the ask grows with how much was actually read.
SENTENCES_PER_PAGE = 1
MIN_SENTENCES = 5

# The ceiling is the generator's output budget, not a stylistic choice. get_generator_llm
# defaults to max_tokens=1024 inside a 4096-token window, and ~20 tokens a sentence puts
# the hard limit near 50 -- asking past that gets a summary cut off mid-word. Raise
# LEARNMATE_GENERATOR_N_CTX and the max_tokens default together before raising this.
MAX_SENTENCES = 30

# Rough length of one summary sentence, used to budget an intermediate fold from the
# amount of text it is being handed. Only needs to be the right order of magnitude.
CHARS_PER_SENTENCE = 120


def _summarise(source: str, sentences: int, doc_id) -> str:
    """One un-judged, un-stored summary pass. Empty string when the generation failed."""
    result = generate_resource(
        "summary", source, count=sentences, doc_id=doc_id,
        evaluate=False, persist=False, verbose=False)
    return (result.get("content") or "").strip()


def _fold_sentences(batch: List[str]) -> int:
    """Sentences to ask of one intermediate fold: about half the content it consumes."""
    return max(PAGE_SENTENCES,
               min(MAX_SENTENCES, sum(len(text) for text in batch) // CHARS_PER_SENTENCE // 2))


def summarize_document(doc_id, count: int = None, threshold: int = None,
                       max_attempts: int = None, evaluate: bool = True,
                       persist: bool = True, verbose: bool = True,
                       max_chars: int = None) -> Dict:
    """
    Summarise every page of a document and combine them into one comprehensive summary.

    count   -- roughly how many sentences to write. None sizes it to the document:
               about one sentence per page read, floored at MIN_SENTENCES and capped at
               MAX_SENTENCES by what the generator can emit in one reply.
    Everything else means what it does on `generate_resource`, and applies to the final
    fold only -- the per-page pass is never judged or stored.

    Returns generate_resource's dict with one extra key, `pages`: the per-page summaries
    as [{"page_number": n, "summary": "..."}], so a caller can show the working rather
    than only the conclusion.

    Raises ValueError when the document has no stored page text, which means it was never
    ingested (or was ingested before store_pages existed -- re-ingest it).
    """
    budget = max_chars or config.MAX_SOURCE_CHARS

    records = pdf_store.get_pages(doc_id)
    if not records:
        raise ValueError(f"No stored page text for document {doc_id}. Ingest the PDF first.")

    # --- Pass 1: one summary per page --------------------------------------------------
    pages: List[Dict] = []
    for record in records:
        text = (record.get("text") or "").strip()
        if len(text) < MIN_PAGE_CHARS:
            continue

        _log({"verbose": verbose}, f"[*] Summarising page {record['page_number']}...")
        # Truncated because one page can still exceed the window on a dense layout.
        summary = _summarise(text[:budget], PAGE_SENTENCES, doc_id)
        if summary:
            pages.append({"page_number": record["page_number"], "summary": summary})

    if not pages:
        raise ValueError(f"Document {doc_id} has no page with enough text to summarise.")

    # How long the answer should be, now that we know how much was actually read.
    sentences = count or max(MIN_SENTENCES,
                             min(MAX_SENTENCES, len(pages) * SENTENCES_PER_PAGE))

    # --- Pass 2: fold until the notes fit one prompt ------------------------------------
    # Page numbers are kept in the text so the fold can say "the opening chapters" rather
    # than treating n paragraphs as n unrelated documents.
    notes = [f"Page {page['page_number']}: {page['summary']}" for page in pages]

    while True:
        batches = batched(notes, budget)
        # One batch means everything fits, so the next pass is the final one. `>=` is the
        # no-progress guard: a single note over the budget would otherwise loop forever.
        if len(batches) <= 1 or len(batches) >= len(notes):
            break
        _log({"verbose": verbose},
             f"[*] Folding {len(notes)} page summaries into {len(batches)}...")
        # Half the content the batch went in with, measured in characters rather than in
        # notes: a batch of four long notes still holds a chapter's worth of material, and
        # counting notes would ask it for two sentences. An intermediate fold is not the
        # answer and only has to shrink -- halving is what makes the loop converge -- but
        # a flat budget here is where the detail was being thrown away, before the final
        # pass ever saw it.
        notes = [_summarise("\n\n".join(batch), _fold_sentences(batch), doc_id)
                 for batch in batches]
        notes = [note for note in notes if note]

    # --- The one pass that is judged and stored -----------------------------------------
    _log({"verbose": verbose},
         f"[*] Writing the document summary from {len(pages)} pages "
         f"(about {sentences} sentences)...")
    result = generate_resource(
        "summary", "\n\n".join(notes)[:budget], count=sentences, doc_id=doc_id,
        threshold=threshold, max_attempts=max_attempts, evaluate=evaluate,
        persist=persist, verbose=verbose)

    result["pages"] = pages
    return result
