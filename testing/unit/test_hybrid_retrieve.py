"""U-19 — BM25/ANN hybrid merge (`learnmate/chat_agent/retrieve.py::_merge_hybrid`).

Pure function: no Qdrant, no Mongo. Exercises the dedup-by-chunk-key and "both" tagging
that `retrieval_mix` (logged per turn, see LATENCY_QUALITY_FAILURES.md) depends on.
"""

from __future__ import annotations

from langchain_core.documents import Document

from learnmate.chat_agent.retrieve import _merge_hybrid
from learnmate.retrieval.bm25 import BM25Okapi


def _doc(page: int, chunk: int, text: str) -> Document:
    return Document(page_content=text, metadata={"page_number": page, "chunk_index": chunk})


def test_a_chunk_found_by_both_ann_and_bm25_is_tagged_both_and_kept_once():
    shared = _doc(1, 0, "directors owe fiduciary duties to the company")
    ann_only = _doc(2, 0, "unrelated recital about definitions")
    bm25_only = _doc(3, 0, "directors fiduciary duties detailed obligations")

    ann_hits = [(shared, 0.9), (ann_only, 0.4)]
    bm25_docs = [shared, bm25_only]
    index = BM25Okapi([
        [t.lower() for t in shared.page_content.split()],
        [t.lower() for t in bm25_only.page_content.split()],
    ])

    scored, mix = _merge_hybrid(ann_hits, bm25_docs, "fiduciary duties of directors", index)
    merged = [doc for doc, _score in scored]

    sources = {doc.metadata["retrieval_source"]: doc for doc in merged}
    assert "both" in sources
    assert sources["both"].page_content == shared.page_content
    # exactly one copy of the shared chunk, not two
    assert sum(1 for d in merged if d.page_content == shared.page_content) == 1
    assert mix["merged"] == len(merged) == 3
    assert mix["ann"] + mix["bm25"] + mix["both"] == mix["merged"]


def test_ann_only_hits_are_capped_at_bm25_ann_keep():
    from learnmate import config

    docs = [_doc(i, 0, f"chunk number {i} about contract law") for i in range(config.BM25_ANN_KEEP + 5)]
    ann_hits = [(doc, 1.0 - i * 0.01) for i, doc in enumerate(docs)]
    # Query shares no terms with this one-entry corpus, so BM25Okapi.ranked() returns
    # [] (it filters to score > 0) and bm25_docs is never indexed into.
    index = BM25Okapi([["nothing", "matches"]])

    merged, mix = _merge_hybrid(ann_hits, [], "unrelated query text", index)

    assert mix["ann"] == config.BM25_ANN_KEEP
    assert len(merged) == config.BM25_ANN_KEEP


def test_empty_ann_and_bm25_returns_empty_merge():
    index = BM25Okapi([["placeholder"]])
    merged, mix = _merge_hybrid([], [], "anything", index)
    assert merged == []
    assert mix["merged"] == 0
