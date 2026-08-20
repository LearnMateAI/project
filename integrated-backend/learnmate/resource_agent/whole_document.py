"""
Generating a list-shaped resource across a whole document.

`generate_resource` sees one passage: MAX_SOURCE_CHARS of text, answered in one reply of
at most 1024 tokens. Both limits bite as soon as the ask is "for this PDF" rather than
"for this passage" -- nothing past the opening pages is ever read, and a large set comes
back truncated mid-item. So the document is split into groups of whole pages, each group
is asked for its share, and the results are pooled.

Two ways to decide the share, because the two questions callers actually ask are different:

    count=40      a set of forty questions *about the document*. Forty questions buys five
                  reads, so five groups are sampled evenly across it.
    per_page=2    two key points *for every page*. The rate is a promise about coverage,
                  so every group is read and the total follows from the page count.

Each group goes through the normal graph and gets the structural gate, the judge and the
retry it would have got on its own. What this module adds is the part no single call can
do: spreading the work across the document, dropping items two groups both produced, and
running gate 1 over the *pooled* set -- the answer always in slot B is invisible inside a
batch of eight and obvious across forty.

    whole_document.py  this: page loading, grouping, the pooled run
    document_mcqs.py   the count-based entry point for mcq
    document_summary.py  summaries, which fold rather than pool and so only borrow the
                         page loading and the grouping
"""

import math
from typing import Dict, List, Optional, Tuple

from .. import config
from ..evaluator import validators
from ..evaluator.normalise import norm
from ..storage import content_store, pdf_store
from .agent import generate_resource
from .helpers import _log

# Pages shorter than this are a title page, a running head or a stray caption -- there is
# no prose on them to work from, and asking anyway spends a generation to be told so.
MIN_PAGE_CHARS = 200

# Items one generation call is asked for at most, by task. The generator emits at most
# max_tokens=1024, and these are that budget divided by what one item costs as JSON: an
# MCQ ~90 tokens (stem, four options, answer, keys), a practice question ~70 (question and
# a one-or-two sentence answer), a key point ~35 (one sentence). A call asked for
# materially more than its entry returns a set cut off partway through.
MAX_PER_CALL = {"mcq": 8, "practice_qsn": 10, "keypoints": 16}
DEFAULT_MAX_PER_CALL = 8

# Floors, where a task's own gate 1 refuses a set that small. validate_keypoints rejects a
# set of one outright, so a trailing group of a single page at one point per page would
# fail the gate for being exactly what it was asked for. Only tasks listed here get a
# floor: the others would just be over-delivering.
MIN_PER_CALL = {"keypoints": 2}

# Smallest group worth generating from. Dividing a short document into one group per call
# can leave each with a paragraph, and questions written from a paragraph are trivia.
MIN_GROUP_CHARS = 1200

# What the CLI offers for a per-page rate. Not a limit: any rate can be passed directly.
PER_PAGE_CHOICES = (1, 2, 4)
DEFAULT_PER_PAGE = 2


def load_page_texts(doc_id, purpose: str) -> List[str]:
    """
    The prose of every page worth reading, in reading order.

    `purpose` is a verb for the error message ("summarise", "question"), so a document with
    nothing usable says which thing it could not be used for.

    Raises ValueError when there is no stored page text, which means the document was never
    ingested (or was ingested before store_pages existed -- re-ingest it).
    """
    records = pdf_store.get_pages(doc_id)
    if not records:
        raise ValueError(f"No stored page text for document {doc_id}. Ingest the PDF first.")

    texts = [text for text in ((record.get("text") or "").strip() for record in records)
             if len(text) >= MIN_PAGE_CHARS]
    if not texts:
        raise ValueError(f"Document {doc_id} has no page with enough text to {purpose}.")
    return texts


def batched(texts: List[str], max_chars: int, max_count: int = None) -> List[List[str]]:
    """
    Group in reading order into runs bounded by size and, optionally, by how many.

    Order is preserved rather than packed for density: a group of pages 1-8 reads as a
    section, a group of pages 1, 40 and 97 reads as three non-sequiturs.
    """
    groups: List[List[str]] = []
    group, size = [], 0
    for text in texts:
        # `group and` keeps a single oversized entry in a group of its own instead of
        # dropping it; the generator truncates it rather than never seeing it.
        full = size + len(text) > max_chars or (max_count and len(group) >= max_count)
        if group and full:
            groups.append(group)
            group, size = [], 0
        group.append(text)
        size += len(text) + 2
    if group:
        groups.append(group)
    return groups


def _stem(task: str, item) -> str:
    """
    What makes two items the same, for deduplication.

    Key points are bare strings and are compared whole; the two question types are
    compared on their stem, because a model asked the same thing twice will word the
    answer differently and the question identically.
    """
    if task == "keypoints":
        return norm(item)
    return norm((item or {}).get("question") if isinstance(item, dict) else item)


def _plan(task: str, texts: List[str], count: Optional[int], per_page: Optional[int],
          budget: int) -> Tuple[List[List[str]], Optional[List[int]], int]:
    """
    Work out the groups, what to ask each of them, and the total being requested.

    Returns (groups, asks, requested). `asks` is None in count mode, where each group's
    share depends on what the groups before it actually produced.
    """
    per_call = MAX_PER_CALL.get(task, DEFAULT_MAX_PER_CALL)

    if per_page:
        # A rate is a promise that every page is read, so the grouping is driven by how
        # many pages' worth of items one call can hold and every group is used.
        groups = batched(texts, budget, max_count=max(1, per_call // per_page))
        floor = MIN_PER_CALL.get(task, 1)
        asks = [max(floor, per_page * len(group)) for group in groups]
        return groups, asks, per_page * len(texts)

    # A total buys a fixed number of calls. Size the groups so there are about that many,
    # clamped to what fits the window and to what is worth generating from.
    calls = max(1, math.ceil(count / per_call))
    total = sum(len(text) + 2 for text in texts)
    groups = batched(texts, min(budget, max(MIN_GROUP_CHARS, math.ceil(total / calls))))

    # A document bigger than `calls` windows cannot be read whole in the calls a set of
    # this size affords -- forty questions buys five reads, and a 400,000-character book is
    # sixty-seven. Sample evenly across it rather than taking the first five groups: one
    # group per fifth of the book is a set about the book, five groups from chapter one is
    # a set about chapter one. The pages between samples are not read; ask for more items
    # to read more of the document.
    if len(groups) > calls:
        step = len(groups) / calls
        groups = [groups[int(index * step)] for index in range(calls)]

    return groups, None, count


def generate_document_items(task: str, doc_id, count: int = None, per_page: int = None,
                            threshold: int = None, max_attempts: int = None,
                            evaluate: bool = True, persist: bool = True,
                            verbose: bool = True, max_chars: int = None,
                            user_id: str = None, on_progress=None,
                            difficulty: str = None, model_id: str = None,
                            summary_style: str = None) -> Dict:
    """
    Generate a list-shaped resource from across a whole document.

    task      -- "mcq", "practice_qsn" or "keypoints". Not "summary": a summary is one
                 artefact and folds rather than pools, so it has its own module.
    count     -- how many items in total, sampled across the document, or
    per_page  -- how many items per page, reading every page. Pass exactly one.

    Everything else means what it does on `generate_resource`. `evaluate` applies per
    group; `persist` stores the pooled set once, not each group.

    Returns generate_resource's dict, with `content` the pooled items and `attempts` every
    group's trail concatenated, plus `requested`, `generated` and `groups`. `accepted` is
    True only when every group was accepted *and* the pooled set passes the structural
    gate: a set can be built entirely from accepted batches and still be biased as a whole.

    Fewer items than requested come back when the document is too short to support them or
    the generator repeated itself; the shortfall is reported, never padded.
    """
    if (count is None) == (per_page is None):
        raise ValueError("Pass exactly one of count= (a total) or per_page= (a rate).")
    if (count or per_page) < 1:
        raise ValueError("count/per_page must be at least 1.")

    budget = max_chars or config.MAX_SOURCE_CHARS
    texts = load_page_texts(doc_id, "question" if task != "keypoints" else "summarise")
    groups, asks, requested = _plan(task, texts, count, per_page, budget)

    _log({"verbose": verbose, "on_progress": on_progress},
         f"[*] {requested} {task} item(s) from {len(texts)} page(s), "
         + (f"at {per_page} per page, " if per_page else "")
         + f"in {len(groups)} group(s)...")

    # --- One call per group -------------------------------------------------------------
    items: List = []
    attempts: List[Dict] = []
    stems = set()
    every_group_accepted = True

    for index, group in enumerate(groups, start=1):
        if asks is not None:
            ask = asks[index - 1]
        else:
            # Share out what is still missing rather than a fixed slice, so a group that
            # came back short is made up for by the ones after it.
            remaining = requested - len(items)
            if remaining <= 0:
                break
            per_call = MAX_PER_CALL.get(task, DEFAULT_MAX_PER_CALL)
            ask = max(1, min(per_call, math.ceil(remaining / (len(groups) - index + 1))))

        _log({"verbose": verbose, "on_progress": on_progress},
             f"[*] Group {index}/{len(groups)}: asking for {ask} item(s)...")
        result = generate_resource(
            task, "\n\n".join(group)[:budget], count=ask, doc_id=doc_id,
            threshold=threshold, max_attempts=max_attempts, evaluate=evaluate,
            persist=False, verbose=verbose, user_id=user_id,
            difficulty=difficulty, model_id=model_id,
            on_progress=(lambda message, n=index: on_progress(
                f"Group {n}/{len(groups)}: {message}")) if on_progress else None)

        attempts.extend(result.get("attempts", []))
        every_group_accepted = every_group_accepted and bool(result.get("accepted"))

        for item in result.get("content") or []:
            # Neighbouring pages routinely produce the same item twice, and every gate 1
            # checker counts a duplicate as a fault.
            stem = _stem(task, item)
            if stem and stem not in stems:
                stems.add(stem)
                items.append(item)

    # A total is a ceiling; a rate is not, since each group was asked for exactly its
    # pages' share and going under it is the only way to miss.
    if count:
        items = items[:count]

    # --- Gate 1 on the pooled set -------------------------------------------------------
    # Cheap, and the only check that can see across groups.
    progress = {"verbose": verbose, "on_progress": on_progress}
    passed, reasons = validators.validate(task, items)
    if not passed:
        _log(progress, f"[!] Pooled set: {'; '.join(reasons)}")
    if len(items) < requested:
        _log(progress, f"[!] Got {len(items)} of the {requested} item(s) asked for.")

    accepted = every_group_accepted and passed

    resource_id = None
    if persist:
        resource_id = content_store.save_resource(
            doc_id=doc_id, user_id=user_id, task=task, content=items, accepted=accepted,
            attempts=attempts, verdict=None,
            source_preview="\n\n".join(groups[0]) if groups else "",
            params={"count": requested, "per_page": per_page, "generated": len(items),
                    "groups": len(groups), "evaluated": evaluate, "whole_document": True,
                    "difficulty": difficulty, "model_id": model_id,
                    "threshold": threshold if threshold is not None
                    else config.EVALUATOR_THRESHOLD})
        _log(progress, f"[+] Stored resource {resource_id}")

    return {
        "task": task,
        "content": items,
        "accepted": accepted,
        # No single verdict: each group was judged on its own and the trail is in
        # `attempts`. Reporting one group's score as the set's would be a lie.
        "verdict": None,
        "attempts": attempts,
        "resource_id": str(resource_id) if resource_id else None,
        "requested": requested,
        "generated": len(items),
        "groups": len(groups),
        "per_page": per_page,
    }
