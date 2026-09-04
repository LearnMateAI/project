"""
Score embedders, rerankers, and hybrid mix on a real legal PDF.

Uses the live ingest extract/clean/chunk path. Vectors stay in memory — this does not
write Qdrant or Mongo, and it does not change .env.

Default PDF: integrated-backend/data/Company-law-part1-notes.pdf (the course notes file
that already lives in the backend data folder, not a new toy fixture).
"""

from __future__ import annotations

import argparse
import platform
import time
from pathlib import Path
from typing import Dict, List, Sequence

from common import (
    FIXTURES_DIR,
    RESULTS_DIR,
    REPO_ROOT,
    BACKEND_DIR,
    ensure_backend_on_path,
    load_comparison_registry,
    load_jsonl,
    write_json,
)
from eval_retrieval import (
    _cosine_topk,
    _embed_corpus,
    _load_cross_encoder,
    _mrr,
    _ndcg_at,
    _recall_at,
    _rerank_ids,
    _summarise,
)

ensure_backend_on_path()

from learnmate.ingestion.chunking import pages_to_documents
from learnmate.ingestion.clean import preprocess
from learnmate.retrieval.bm25 import BM25Okapi, tokenize
from learnmate.storage.bm25_store import chunk_key


DEFAULT_PDF = BACKEND_DIR / "data" / "Company-law-part1-notes.pdf"


def _chunk_pdf(pdf_path: Path) -> List[Dict]:
    data = pdf_path.read_bytes()
    pages = preprocess(data)
    docs = pages_to_documents(pages, doc_id="real-pdf-eval", filename=pdf_path.name)
    chunks = []
    for i, doc in enumerate(docs):
        meta = doc.metadata or {}
        cid = chunk_key(meta.get("page_number"), meta.get("chunk_index"))
        chunks.append({
            "id": cid or f"c{i:03d}",
            "text": doc.page_content,
            "page_number": meta.get("page_number"),
            "chunk_index": meta.get("chunk_index"),
        })
    return chunks


def _gold_ids(chunks: List[Dict], needles: Sequence[str]) -> List[str]:
    lowered_needles = [n.lower() for n in needles if n]
    hits = []
    for chunk in chunks:
        text = (chunk["text"] or "").lower()
        if any(n in text for n in lowered_needles):
            hits.append(chunk["id"])
    return hits


def _mix_for(ann_ids: Sequence[str], bm25_ids: Sequence[str], kept_ids: Sequence[str]
             ) -> Dict:
    ann_set, bm25_set = set(ann_ids), set(bm25_ids)
    sources = {}
    for cid in ann_ids:
        sources[cid] = "ann"
    for cid in bm25_ids:
        sources[cid] = "both" if cid in sources else "bm25"
    kept = {}
    for cid in kept_ids:
        src = sources.get(cid, "ann")
        kept[src] = kept.get(src, 0) + 1
    return {
        "ann": sum(1 for s in sources.values() if s == "ann"),
        "bm25": sum(1 for s in sources.values() if s == "bm25"),
        "both": sum(1 for s in sources.values() if s == "both"),
        "merged": len(sources),
        "rerank_kept": kept,
    }


def eval_embedders(registry, chunks, queries, k: int = 5) -> Dict:
    ids = [c["id"] for c in chunks]
    reports = []
    for spec in registry["embeddings"]:
        print(f"[*] Embedding {spec['id']} on {len(chunks)} real chunks...")
        model, matrix, encode_ms = _embed_corpus(spec, chunks)
        per_query = []
        q_ms = []
        for query in queries:
            t0 = time.perf_counter()
            qvec = model.embed_query(query["question"])
            q_ms.append((time.perf_counter() - t0) * 1000)
            ranked = _cosine_topk(qvec, matrix, k=len(chunks))
            ranked_ids = [ids[i] for i, _ in ranked]
            gold = query["gold"]
            per_query.append({
                "id": query["id"],
                "gold_n": len(gold),
                "gold_in_top3": _recall_at(ranked_ids, gold, 3),
                "recall@5": _recall_at(ranked_ids, gold, 5),
                "mrr": _mrr(ranked_ids, gold),
                "ndcg@5": _ndcg_at(ranked_ids, gold, 5),
                "rank_gold": next(
                    (i + 1 for i, cid in enumerate(ranked_ids) if cid in gold), None),
                "top3": ranked_ids[:3],
            })
        summary = _summarise(per_query, 5)
        summary.update({
            "id": spec["id"],
            "hf_id": spec["hf_id"],
            "gold_in_top3": round(
                sum(row["gold_in_top3"] for row in per_query) / len(per_query), 4),
            "encode_corpus_ms": round(encode_ms, 1),
            "encode_query_ms_mean": round(sum(q_ms) / len(q_ms), 2) if q_ms else 0,
            "per_query": per_query,
        })
        reports.append(summary)
        print(f"    {spec['id']}: gold_in_top3={summary['gold_in_top3']} "
              f"ndcg@5={summary['ndcg@5']} query_ms={summary['encode_query_ms_mean']}")
    return {"models": reports}


def eval_rerankers_and_mix(registry, chunks, queries, candidate_k: int = 20) -> Dict:
    from learnmate import config

    baseline = next(s for s in registry["embeddings"] if s.get("baseline"))
    embedder, matrix, _ = _embed_corpus(baseline, chunks)
    ids = [c["id"] for c in chunks]
    by_id = {c["id"]: c["text"] for c in chunks}
    bm25 = BM25Okapi([tokenize(c["text"]) for c in chunks])
    ann_keep = int(getattr(config, "BM25_ANN_KEEP", 15))
    bm25_k = int(getattr(config, "BM25_TOP_K", 10))

    reports = []
    for spec in registry["rerankers"]:
        if spec["id"] == "bge-reranker-base":
            print("[*] Skipping BGE reranker-base on the real PDF (already rejected on latency).")
            continue
        model = _load_cross_encoder(spec["hf_id"])
        per_query = []
        predict_ms = []
        mixes = []
        for query in queries:
            qvec = embedder.embed_query(query["question"])
            ann = [ids[i] for i, _ in _cosine_topk(
                qvec, matrix, k=min(ann_keep, len(chunks)))]
            bm25_ids = []
            for i, _score in bm25.ranked(query["question"], bm25_k):
                bm25_ids.append(ids[i])
            pool = []
            seen = set()
            for cid in ann + bm25_ids:
                if cid not in seen:
                    pool.append(cid)
                    seen.add(cid)
            t0 = time.perf_counter()
            ranked_ids = _rerank_ids(
                model, query["question"], pool, by_id, top_k=len(pool))
            predict_ms.append((time.perf_counter() - t0) * 1000)
            gold = query["gold"]
            mix = _mix_for(ann, bm25_ids, ranked_ids[:3])
            mixes.append(mix)
            per_query.append({
                "id": query["id"],
                "gold_in_top3": _recall_at(ranked_ids, gold, 3),
                "recall@5": _recall_at(ranked_ids, gold, 5),
                "mrr": _mrr(ranked_ids, gold),
                "ndcg@5": _ndcg_at(ranked_ids, gold, 5),
                "top3": ranked_ids[:3],
                "retrieval_mix": mix,
            })
        n = len(mixes) or 1
        kept_bm25 = sum(m["rerank_kept"].get("bm25", 0) for m in mixes)
        kept_both = sum(m["rerank_kept"].get("both", 0) for m in mixes)
        kept_ann = sum(m["rerank_kept"].get("ann", 0) for m in mixes)
        summary = _summarise(per_query, 5)
        summary.update({
            "id": spec["id"],
            "hf_id": spec["hf_id"],
            "gold_in_top3": round(
                sum(row["gold_in_top3"] for row in per_query) / len(per_query), 4),
            "predict_ms_mean": round(sum(predict_ms) / len(predict_ms), 1),
            "retrieval_mix_totals": {
                "ann_only_in_pool_mean": round(sum(m["ann"] for m in mixes) / n, 2),
                "bm25_only_in_pool_mean": round(sum(m["bm25"] for m in mixes) / n, 2),
                "both_in_pool_mean": round(sum(m["both"] for m in mixes) / n, 2),
                "rerank_kept_top3": {
                    "ann": kept_ann, "bm25": kept_bm25, "both": kept_both,
                },
            },
            "per_query": per_query,
        })
        reports.append(summary)
        print(f"    {spec['id']}: gold_in_top3={summary['gold_in_top3']} "
              f"ndcg@5={summary['ndcg@5']} predict_ms={summary['predict_ms_mean']}")
        print(f"    mix kept top-3: {summary['retrieval_mix_totals']['rerank_kept_top3']}")
    return {"models": reports, "pool": "hybrid MiniLM + BM25"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf", default=str(DEFAULT_PDF))
    args = parser.parse_args()

    pdf_path = Path(args.pdf)
    if not pdf_path.is_file():
        raise SystemExit(f"PDF not found: {pdf_path}")

    chunks = _chunk_pdf(pdf_path)
    raw_queries = load_jsonl(FIXTURES_DIR / "real_pdf_queries.jsonl")
    queries = []
    skipped = []
    for row in raw_queries:
        gold = _gold_ids(chunks, row.get("gold_contains") or [])
        if not gold:
            skipped.append(row["id"])
            continue
        queries.append({**row, "gold": gold})
    print(f"[*] PDF {pdf_path.name}: {len(chunks)} chunks, {len(queries)} queries "
          f"with gold ({skipped} had no matching chunk)")

    registry = load_comparison_registry()
    payload = {
        "pdf": str(pdf_path.relative_to(REPO_ROOT) if pdf_path.is_relative_to(REPO_ROOT)
                   else pdf_path),
        "n_chunks": len(chunks),
        "n_queries": len(queries),
        "queries_without_gold": skipped,
        "machine": {
            "system": platform.system(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "note": "Laptop CPU in-process retrieve; not uvicorn chat p95, not Colab T4.",
        },
        "embeddings": eval_embedders(registry, chunks, queries),
        "rerankers": eval_rerankers_and_mix(registry, chunks, queries),
        "live_env": {
            "LEARNMATE_RERANK_MODEL": "not changed",
            "LEARNMATE_EMBEDDING_MODEL": "not changed",
            "reason": (
                "In-process ablation on the same chunker/embedder/reranker classes as the "
                "app. Live .env was left on MiniLM-L6 + L-6 so a re-ingest was not required "
                "and mixed MiniLM/E5 vectors were never written to Qdrant."
            ),
        },
    }
    out = RESULTS_DIR / "real_pdf.json"
    write_json(out, payload)
    print(f"[*] Wrote {out}")


if __name__ == "__main__":
    main()
