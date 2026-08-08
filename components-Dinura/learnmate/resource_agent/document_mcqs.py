"""
A question set covering a whole document, not just the passage that fits the window.

`generate_resource("mcq", source, count=40)` cannot deliver forty questions, for two
separate reasons. It only ever sees MAX_SOURCE_CHARS of the document, so nothing past the
opening pages can be asked about; and forty questions is far more JSON than the generator's
1024-token reply can hold, so the set comes back truncated mid-question. Asking for a big
number from one call fails quietly -- you get eight questions about page three.

So the document is split into groups of whole pages, each group is asked for its share,
and the results are pooled:

    pages 1-12  --> 8 questions --+
    pages 13-24 --> 8 questions --+--> deduplicated, trimmed to the count asked for
    pages 25-36 --> 8 questions --+

Each group goes through the normal graph, so every batch gets the structural gate, the
judge and the retry it would have got on its own. What this module adds on top is the
part no single call can do: spreading the questions across the whole document, dropping
questions two groups happened to both ask, and checking the *pooled* set for the biases
that only exist across a set -- the answer always in slot B is invisible inside a batch of
eight and obvious across forty.
"""

import math
from typing import Dict, List

from .. import config
from ..evaluator import validators
from ..evaluator.normalise import norm
from ..storage import content_store, pdf_store
from .agent import generate_resource
from .document_summary import MIN_PAGE_CHARS, _batched
from .helpers import _log

# Questions asked of a single generation call. One MCQ costs ~90 tokens as JSON -- the
# stem, four options, the answer and the keys around them -- against a 1024-token reply
# budget, so a call asked for many more than this returns a set cut off partway through.
MAX_PER_CALL = 8

# Smallest group worth asking a question about. Dividing a short document into one group
# per call can leave each with a paragraph, and questions written from a paragraph are
# trivia. Below this the groups are made fewer and larger, and the shortfall is reported.
MIN_GROUP_CHARS = 1200

# What the CLI offers. Not a limit: any count can be passed directly.
COUNT_CHOICES = (10, 20, 40)
DEFAULT_COUNT = 20


def generate_document_mcqs(doc_id, count: int = DEFAULT_COUNT, threshold: int = None,
                           max_attempts: int = None, evaluate: bool = True,
                           persist: bool = True, verbose: bool = True,
                           max_chars: int = None) -> Dict:
    """
    Write `count` multiple-choice questions drawn from across the whole document.

    count   -- how many questions in total. Split across as many generation calls as it
               takes, since one call cannot exceed MAX_PER_CALL.
    Everything else means what it does on `generate_resource`. `evaluate` applies per
    group; `persist` stores the pooled set once, not each group.

    Returns generate_resource's dict, with `content` the pooled questions and `attempts`
    every group's trail concatenated. `accepted` is True only when every group was
    accepted *and* the pooled set passes the structural gate -- a set can be built
    entirely from accepted batches and still be biased as a whole.

    Fewer than `count` questions come back when the document is too short to support them
    or the generator kept repeating itself; the shortfall is logged rather than padded.

    Raises ValueError when the document has no stored page text, which means it was never
    ingested (or was ingested before store_pages existed -- re-ingest it).
    """
    budget = max_chars or config.MAX_SOURCE_CHARS

    records = pdf_store.get_pages(doc_id)
    if not records:
        raise ValueError(f"No stored page text for document {doc_id}. Ingest the PDF first.")

    # Same filter as the page summaries: a title page has nothing to ask a question about.
    texts = [text for text in ((record.get("text") or "").strip() for record in records)
             if len(text) >= MIN_PAGE_CHARS]
    if not texts:
        raise ValueError(f"Document {doc_id} has no page with enough text to question.")

    # --- Split the document into one group per generation call --------------------------
    # Three limits decide the grouping: a group must fit the context window, there must be
    # enough groups that no call is asked for more than it can emit, and a group must hold
    # enough text to be worth a question. Sizing by the second and clamping to the other
    # two satisfies all three, and spreads the questions across the document instead of
    # taking them all from the opening chapters.
    calls = max(1, math.ceil(count / MAX_PER_CALL))
    total = sum(len(text) + 2 for text in texts)
    target = min(budget, max(MIN_GROUP_CHARS, math.ceil(total / calls)))
    groups = _batched(texts, target)

    # A document bigger than `calls` windows cannot be read whole in the calls a set of
    # this size affords -- forty questions buys five reads, and a 400,000-character book is
    # sixty-seven. Sample evenly across it rather than taking the first five groups: one
    # group per fifth of the book is a set about the book, five groups from chapter one is
    # a set about chapter one. The pages between samples are not questioned; ask for more
    # questions to read more of the document.
    if len(groups) > calls:
        step = len(groups) / calls
        groups = [groups[int(index * step)] for index in range(calls)]

    _log({"verbose": verbose},
         f"[*] {count} questions from {len(texts)} pages, in {len(groups)} group(s)...")

    # --- One call per group -------------------------------------------------------------
    questions: List[Dict] = []
    attempts: List[Dict] = []
    stems = set()
    every_group_accepted = True

    for index, group in enumerate(groups, start=1):
        # Share out what is still missing rather than a fixed slice: a group that came
        # back short is made up for by the ones after it.
        remaining = count - len(questions)
        if remaining <= 0:
            break
        ask = max(1, min(MAX_PER_CALL, math.ceil(remaining / (len(groups) - index + 1))))

        _log({"verbose": verbose},
             f"[*] Group {index}/{len(groups)}: asking for {ask} question(s)...")
        result = generate_resource(
            "mcq", "\n\n".join(group)[:budget], count=ask, doc_id=doc_id,
            threshold=threshold, max_attempts=max_attempts, evaluate=evaluate,
            persist=False, verbose=verbose)

        attempts.extend(result.get("attempts", []))
        every_group_accepted = every_group_accepted and bool(result.get("accepted"))

        for item in result.get("content") or []:
            # Deduplicated on the stem: two groups covering neighbouring pages routinely
            # ask the same question, and validate_mcq_set counts that as a fault.
            stem = norm(item.get("question"))
            if stem and stem not in stems:
                stems.add(stem)
                questions.append(item)

    questions = questions[:count]

    # --- Gate 1 on the pooled set -------------------------------------------------------
    # Cheap, and it is the only check that can see across groups.
    passed, reasons = validators.validate("mcq", questions)
    if not passed:
        _log({"verbose": verbose}, f"[!] Pooled set: {'; '.join(reasons)}")
    if len(questions) < count:
        _log({"verbose": verbose},
             f"[!] Got {len(questions)} of the {count} questions asked for.")

    accepted = every_group_accepted and passed

    resource_id = None
    if persist:
        resource_id = content_store.save_resource(
            doc_id=doc_id, task="mcq", content=questions, accepted=accepted,
            attempts=attempts, verdict=None,
            source_preview="\n\n".join(groups[0]) if groups else "",
            params={"count": count, "generated": len(questions), "groups": len(groups),
                    "threshold": threshold if threshold is not None
                    else config.EVALUATOR_THRESHOLD,
                    "evaluated": evaluate, "whole_document": True})
        _log({"verbose": verbose}, f"[+] Stored resource {resource_id}")

    return {
        "task": "mcq",
        "content": questions,
        "accepted": accepted,
        # No single verdict: each group was judged separately, and the trail is in
        # `attempts`. Reporting one group's score as the set's would be a lie.
        "verdict": None,
        "attempts": attempts,
        "resource_id": str(resource_id) if resource_id else None,
        "requested": count,
        "groups": len(groups),
    }
