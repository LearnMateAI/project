"""
Score embedders, rerankers, and retrieve agents on fixtures/legal_retrieval.jsonl.

Does not start FastAPI, Mongo, or Qdrant. Vectors live in memory for this fixture only.
Does not load the process-wide embeddings singleton — each candidate is constructed with
its own model name and prefixes.
"""

from __future__ import annotations

import argparse
import math
import time
from typing import Dict, List, Sequence, Tuple

from common import (
    FIXTURES_DIR,
    RESULTS_DIR,
    ensure_backend_on_path,
    load_comparison_registry,
    load_jsonl,
    write_json,
)

ensure_backend_on_path()

import numpy as np
from langchain_core.documents import Document

from learnmate.llm.embeddings import LearnMateEmbeddings
from learnmate.llm.rerank import _sigmoid
from learnmate.retrieval.bm25 import BM25Okapi, tokenize


def _split_fixture(rows):
    chunks = [row for row in rows if row.get("kind") == "chunk"]
    queries = [row for row in rows if row.get("kind") == "query"]
    return chunks, queries


def _cosine_topk(query_vec, doc_matrix, k: int) -> List[Tuple[int, float]]:
    scores = doc_matrix @ np.asarray(query_vec, dtype=np.float32)
    order = np.argsort(-scores)[:k]
    return [(int(i), float(scores[i])) for i in order]


def _recall_at(ranked_ids: Sequence[str], gold: Sequence[str], k: int) -> float:
    top = set(ranked_ids[:k])
    return 1.0 if any(g in top for g in gold) else 0.0


def _mrr(ranked_ids: Sequence[str], gold: Sequence[str]) -> float:
    gold_set = set(gold)
    for i, cid in enumerate(ranked_ids, start=1):
        if cid in gold_set:
            return 1.0 / i
    return 0.0


def _ndcg_at(ranked_ids: Sequence[str], gold: Sequence[str], k: int) -> float:
    gold_set = set(gold)
    dcg = 0.0
    for i, cid in enumerate(ranked_ids[:k], start=1):
        rel = 1.0 if cid in gold_set else 0.0
        dcg += rel / math.log2(i + 1)
    ideal_hits = min(k, len(gold_set))
    idcg = sum(1.0 / math.log2(i + 1) for i in range(1, ideal_hits + 1))
    return (dcg / idcg) if idcg else 0.0


def _summarise(per_query: List[Dict], k: int = 5) -> Dict:
    n = len(per_query) or 1
    return {
        f"recall@{k}": round(sum(row[f"recall@{k}"] for row in per_query) / n, 4),
        "mrr": round(sum(row["mrr"] for row in per_query) / n, 4),
        f"ndcg@{k}": round(sum(row[f"ndcg@{k}"] for row in per_query) / n, 4),
        "n_queries": len(per_query),
    }


def _embed_corpus(spec: Dict, chunks: List[Dict]) -> Tuple[LearnMateEmbeddings, np.ndarray, float]:
    model = LearnMateEmbeddings(
        model_name=spec["hf_id"],
        query_prefix=spec.get("query_prefix") or "",
        doc_prefix=spec.get("doc_prefix") or "",
    )
    started = time.perf_counter()
    vectors = model.embed_documents([c["text"] for c in chunks])
    elapsed_ms = (time.perf_counter() - started) * 1000
    matrix = np.asarray(vectors, dtype=np.float32)
    return model, matrix, elapsed_ms


def eval_embeddings(registry, chunks, queries, k: int = 5) -> Dict:
    ids = [c["id"] for c in chunks]
    reports = []
    for spec in registry["embeddings"]:
        print(f"[*] Embedding {spec['id']} ({spec['hf_id']})...")
        model, matrix, encode_ms = _embed_corpus(spec, chunks)
        per_query = []
        q_ms = []
        for query in queries:
            t0 = time.perf_counter()
            qvec = model.embed_query(query["text"])
            q_ms.append((time.perf_counter() - t0) * 1000)
            ranked = _cosine_topk(qvec, matrix, k=len(chunks))
            ranked_ids = [ids[i] for i, _ in ranked]
            gold = query["gold"]
            per_query.append({
                "id": query["id"],
                "want": query.get("want"),
                f"recall@{k}": _recall_at(ranked_ids, gold, k),
                "mrr": _mrr(ranked_ids, gold),
                f"ndcg@{k}": _ndcg_at(ranked_ids, gold, k),
                "rank_gold": next(
                    (i + 1 for i, cid in enumerate(ranked_ids) if cid in gold), None),
            })
        summary = _summarise(per_query, k)
        summary.update({
            "id": spec["id"],
            "display_name": spec.get("display_name"),
            "baseline": bool(spec.get("baseline")),
            "hf_id": spec["hf_id"],
            "dim": int(matrix.shape[1]),
            "encode_corpus_ms": round(encode_ms, 1),
            "encode_query_ms_mean": round(sum(q_ms) / len(q_ms), 2) if q_ms else 0,
            "per_query": per_query,
        })
        reports.append(summary)
        print(f"    recall@{k}={summary[f'recall@{k}']} mrr={summary['mrr']} "
              f"ndcg@{k}={summary[f'ndcg@{k}']} dim={summary['dim']}")
    return {"k": k, "models": reports}


def _load_cross_encoder(hf_id: str):
    from sentence_transformers import CrossEncoder
    print(f"[*] Reranker {hf_id}...")
    return CrossEncoder(hf_id)


def _rerank_ids(model, query_text: str, candidate_ids: List[str],
                by_id: Dict[str, str], top_k: int) -> List[str]:
    pairs = [(query_text, by_id[cid]) for cid in candidate_ids]
    logits = model.predict(pairs, show_progress_bar=False)
    scored = sorted(
        zip(candidate_ids, [_sigmoid(float(x)) for x in logits]),
        key=lambda item: item[1],
        reverse=True,
    )
    return [cid for cid, _ in scored[:top_k]]


def eval_rerankers(registry, chunks, queries, candidate_k: int = 20, top_k: int = 5) -> Dict:
    """Fixed MiniLM candidate pool so the reranker is the only variable."""
    baseline = next(s for s in registry["embeddings"] if s.get("baseline"))
    print("[*] Building MiniLM candidate pools for reranker ablation...")
    embedder, matrix, _ = _embed_corpus(baseline, chunks)
    ids = [c["id"] for c in chunks]
    by_id = {c["id"]: c["text"] for c in chunks}
    pools = {}
    for query in queries:
        qvec = embedder.embed_query(query["text"])
        ranked = _cosine_topk(qvec, matrix, k=min(candidate_k, len(chunks)))
        pools[query["id"]] = [ids[i] for i, _ in ranked]

    reports = []
    for spec in registry["rerankers"]:
        model = _load_cross_encoder(spec["hf_id"])
        per_query = []
        predict_ms = []
        for query in queries:
            t0 = time.perf_counter()
            ranked_ids = _rerank_ids(
                model, query["text"], pools[query["id"]], by_id, top_k=len(pools[query["id"]]))
            predict_ms.append((time.perf_counter() - t0) * 1000)
            gold = query["gold"]
            per_query.append({
                "id": query["id"],
                "want": query.get("want"),
                "recall@5": _recall_at(ranked_ids, gold, 5),
                "gold_in_top3": _recall_at(ranked_ids, gold, 3),
                "mrr": _mrr(ranked_ids, gold),
                "ndcg@5": _ndcg_at(ranked_ids, gold, 5),
            })
        summary = _summarise(per_query, 5)
        summary.update({
            "id": spec["id"],
            "display_name": spec.get("display_name"),
            "baseline": bool(spec.get("baseline")),
            "hf_id": spec["hf_id"],
            "gold_in_top3": round(
                sum(row["gold_in_top3"] for row in per_query) / len(per_query), 4),
            "predict_20_pairs_ms_mean": round(sum(predict_ms) / len(predict_ms), 1),
            "candidate_k": candidate_k,
            "per_query": per_query,
        })
        reports.append(summary)
        print(f"    {spec['id']}: recall@5={summary['recall@5']} "
              f"gold_in_top3={summary['gold_in_top3']} ndcg@5={summary['ndcg@5']}")
    return {"candidate_k": candidate_k, "pool": "minilm-l6", "models": reports}


def eval_agents(registry, chunks, queries, top_k: int = 5) -> Dict:
    """ANN-rerank vs hybrid-rerank on MiniLM + baseline cross-encoder."""
    from learnmate import config

    embed_spec = next(s for s in registry["embeddings"] if s.get("baseline"))
    rerank_spec = next(s for s in registry["rerankers"] if s.get("baseline"))
    embedder, matrix, _ = _embed_corpus(embed_spec, chunks)
    reranker = _load_cross_encoder(rerank_spec["hf_id"])
    ids = [c["id"] for c in chunks]
    by_id = {c["id"]: c["text"] for c in chunks}
    bm25 = BM25Okapi([tokenize(c["text"]) for c in chunks])
    ann_keep = int(getattr(config, "BM25_ANN_KEEP", 15))
    bm25_k = int(getattr(config, "BM25_TOP_K", 10))
    rerank_candidates = int(getattr(config, "RERANK_CANDIDATES", 20))

    def ann_pool(query_text: str) -> List[str]:
        qvec = embedder.embed_query(query_text)
        ranked = _cosine_topk(qvec, matrix, k=min(rerank_candidates, len(chunks)))
        return [ids[i] for i, _ in ranked]

    def hybrid_pool(query_text: str) -> List[str]:
        qvec = embedder.embed_query(query_text)
        ann = _cosine_topk(qvec, matrix, k=min(ann_keep, len(chunks)))
        ordered = []
        seen = set()
        for i, _ in ann:
            cid = ids[i]
            ordered.append(cid)
            seen.add(cid)
        for i, _score in bm25.ranked(query_text, bm25_k):
            cid = ids[i]
            if cid not in seen:
                ordered.append(cid)
                seen.add(cid)
        return ordered

    reports = []
    for spec in registry["agents"]:
        pool_fn = hybrid_pool if spec.get("hybrid_bm25") else ann_pool
        per_query = []
        mix = []
        for query in queries:
            pool = pool_fn(query["text"])
            ranked_ids = _rerank_ids(reranker, query["text"], pool, by_id, top_k=len(pool))
            gold = query["gold"]
            per_query.append({
                "id": query["id"],
                "want": query.get("want"),
                "pool_size": len(pool),
                "recall@5": _recall_at(ranked_ids, gold, 5),
                "gold_in_top3": _recall_at(ranked_ids, gold, 3),
                "mrr": _mrr(ranked_ids, gold),
                "ndcg@5": _ndcg_at(ranked_ids, gold, 5),
            })
            mix.append(len(pool))
        summary = _summarise(per_query, 5)
        summary.update({
            "id": spec["id"],
            "display_name": spec.get("display_name"),
            "baseline": bool(spec.get("baseline")),
            "hybrid_bm25": bool(spec.get("hybrid_bm25")),
            "gold_in_top3": round(
                sum(row["gold_in_top3"] for row in per_query) / len(per_query), 4),
            "mean_pool_size": round(sum(mix) / len(mix), 2) if mix else 0,
            "embedder": embed_spec["id"],
            "reranker": rerank_spec["id"],
            "per_query": per_query,
        })
        reports.append(summary)
        print(f"    {spec['id']}: recall@5={summary['recall@5']} "
              f"mrr={summary['mrr']} gold_in_top3={summary['gold_in_top3']}")
    return {"models": reports}


def _pick_winners(payload: Dict) -> Dict:
    def best(rows, key):
        return max(rows, key=lambda row: (row[key], -int(row.get("baseline") or 0)))["id"]

    return {
        "embeddings_by_ndcg@5": best(payload["embeddings"]["models"], "ndcg@5"),
        "rerankers_by_ndcg@5": best(payload["rerankers"]["models"], "ndcg@5"),
        "agents_by_ndcg@5": best(payload["agents"]["models"], "ndcg@5"),
        "note": (
            "Winners on this fixture only. Do not change selectable_default until "
            "RESULTS.md records a full-product decision. Ties prefer the non-baseline."
        ),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-rerankers", action="store_true")
    parser.add_argument("--skip-agents", action="store_true")
    args = parser.parse_args()

    registry = load_comparison_registry()
    chunks, queries = _split_fixture(load_jsonl(FIXTURES_DIR / "legal_retrieval.jsonl"))
    print(f"[*] Fixture: {len(chunks)} chunks, {len(queries)} queries")

    payload = {
        "fixture": str(FIXTURES_DIR / "legal_retrieval.jsonl"),
        "embeddings": eval_embeddings(registry, chunks, queries),
    }
    if not args.skip_rerankers:
        payload["rerankers"] = eval_rerankers(registry, chunks, queries)
    if not args.skip_agents:
        payload["agents"] = eval_agents(registry, chunks, queries)
    payload["fixture_winners"] = _pick_winners(payload)

    out = RESULTS_DIR / "retrieval.json"
    write_json(out, payload)
    print(f"[*] Wrote {out}")
    print("[*] Fixture winners:", payload["fixture_winners"])


if __name__ == "__main__":
    main()
