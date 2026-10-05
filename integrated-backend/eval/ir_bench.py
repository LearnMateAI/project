"""
Retrieval quality and latency for every strategy, with and without the reranker.

    python -m eval.ir_bench [--strategies legacy dense bm25 rrf dbsf] [--k 20]

Queries are the workload's seed questions and their paraphrases (eval/workload.py), each
labelled with the chunk it was written from. For every query and strategy:

    first stage   retriever.search(query, doc, k=20, strategy)        (the production call)
    + rerank      the cross-encoder over those 20, as the chat agent does

and the ranking is scored against the gold chunk: Recall@1/3/10 (3 is what reaches the
prompt), MRR@10, and nDCG@10 with graded relevance (gold chunk 2, same page 1). Latency is
the first stage (embedding the query included) and the rerank, separately.

Also measured: the pdf/general decision. Each document is asked its own seed questions
(which it can answer: pdf mode is right) and seed questions written for *other* chapters
(general mode is right), under the production rule -- reranker score >= 0.5.

Seeds and paraphrases are reported separately: seeds share more words with their chunk
(see workload.py), so they flatter lexical retrieval; paraphrases are the fairer test.
Significance is a paired bootstrap against `legacy` on the same queries.
"""

import argparse
import random
import sys
import time
from collections import defaultdict

from eval.common import WORKLOAD_DIR, bootstrap, provenance, read_jsonl, run_dir, write_json
from eval.metrics import (bootstrap_ci, latency_summary, mean, mrr_at_k, ndcg_at_k,
                          paired_bootstrap, recall_at_k)

METRICS = ("r@1", "r@3", "r@10", "mrr@10", "ndcg@10", "page_r@3")


def _score(ranked_keys, gold_key, gold_page):
    grades = {gold_key: 2}
    page_prefix = f"{gold_page}:"
    for key in ranked_keys:
        if key != gold_key and key.startswith(page_prefix):
            grades[key] = 1
    return {
        "r@1": recall_at_k(ranked_keys, [gold_key], 1),
        "r@3": recall_at_k(ranked_keys, [gold_key], 3),
        "r@10": recall_at_k(ranked_keys, [gold_key], 10),
        "mrr@10": mrr_at_k(ranked_keys, [gold_key], 10),
        "ndcg@10": ndcg_at_k(ranked_keys, grades, 10),
        "page_r@3": 1.0 if any(key.startswith(page_prefix) for key in ranked_keys[:3]) else 0.0,
    }


def run(strategies, k: int, seed: int, limit: int = None):
    from learnmate import config
    from learnmate.llm import rerank as reranker
    from learnmate.retrieval import retriever

    questions = [q for q in read_jsonl(WORKLOAD_DIR / "questions.jsonl")
                 if q["variant"] in ("seed", "para")]
    if limit:
        questions = questions[:limit]
    if not reranker.available():
        raise SystemExit("The reranker is needed for this benchmark.")

    # Warm every strategy (and the legacy in-process BM25 index of every document) so the
    # timings below are steady-state, not first-load.
    for doc_id in sorted({q["doc_id"] for q in questions}):
        for strategy in strategies:
            warm = retriever.search("what is the rule", doc_id, k=k, strategy=strategy)
            reranker.rerank("what is the rule", [hit.doc for hit in warm.hits], top_k=3)

    per_query = defaultdict(dict)     # (strategy, rerank) -> qid -> metrics
    latency = defaultdict(list)       # (strategy, stage) -> ms
    ran_as = {}
    for index, q in enumerate(questions):
        for strategy in strategies:
            started = time.perf_counter()
            result = retriever.search(q["text"], q["doc_id"], k=k, strategy=strategy)
            latency[(strategy, "first_stage")].append((time.perf_counter() - started) * 1000)
            ran_as[strategy] = result.strategy
            docs = [hit.doc for hit in result.hits]
            keys = [retriever.chunk_key(doc) for doc in docs]
            per_query[(strategy, False)][q["qid"]] = _score(keys, q["gold_key"], q["gold_page"])

            started = time.perf_counter()
            ranked = reranker.rerank(q["text"], docs, top_k=len(docs)) or []
            latency[(strategy, "rerank")].append((time.perf_counter() - started) * 1000)
            reranked = [retriever.chunk_key(doc) for doc, _ in ranked]
            per_query[(strategy, True)][q["qid"]] = _score(reranked, q["gold_key"],
                                                            q["gold_page"])
        if (index + 1) % 50 == 0:
            print(f"  {index + 1}/{len(questions)} queries")

    by_variant = {q["qid"]: q["variant"] for q in questions}
    by_split = {q["qid"]: q["split"] for q in questions}
    overlap = {q["qid"]: q.get("overlap") for q in questions}

    def aggregate(rows, qids):
        out = {}
        for metric in METRICS:
            values = [rows[qid][metric] for qid in qids]
            low, high = bootstrap_ci(values)
            out[metric] = {"mean": mean(values), "ci95": [low, high]}
        out["n"] = len(qids)
        return out

    subsets = {
        "all": [q["qid"] for q in questions],
        "seed": [q["qid"] for q in questions if q["variant"] == "seed"],
        "para": [q["qid"] for q in questions if q["variant"] == "para"],
        "low_overlap": [q["qid"] for q in questions
                        if q.get("overlap") is not None and q["overlap"] < 0.5],
        "test": [q["qid"] for q in questions if q["split"] == "test"],
    }
    table = {}
    for (strategy, rerank), rows in per_query.items():
        name = f"{strategy}{'+rerank' if rerank else ''}"
        table[name] = {subset: aggregate(rows, qids) for subset, qids in subsets.items()
                       if qids}
        table[name]["ran_as"] = ran_as.get(strategy)
        table[name]["latency_ms"] = {
            "first_stage": latency_summary(latency[(strategy, "first_stage")]),
            "rerank": latency_summary(latency[(strategy, "rerank")]) if rerank else None,
        }

    significance = {}
    if "legacy" in strategies:
        for (strategy, rerank), rows in per_query.items():
            if strategy == "legacy":
                continue
            base = per_query[("legacy", rerank)]
            for metric in ("ndcg@10", "r@3", "mrr@10"):
                for subset in ("all", "para"):
                    qids = subsets[subset]
                    significance[f"{strategy}{'+rerank' if rerank else ''}|{metric}|{subset}"] = \
                        paired_bootstrap([base[q][metric] for q in qids],
                                         [rows[q][metric] for q in qids])

    modes = mode_accuracy(strategies, k, seed)
    return {"table": table, "significance": significance, "mode": modes,
            "n_queries": len(questions), "k": k, "top_k": config.TOP_K,
            "rerank_model": config.RERANK_MODEL, "strategies": strategies}


def mode_accuracy(strategies, k: int, seed: int, per_doc: int = 10):
    """pdf for a document's own questions, general for other chapters' questions."""
    from learnmate.llm import rerank as reranker
    from learnmate.retrieval import retriever

    rng = random.Random(seed)
    seeds = [q for q in read_jsonl(WORKLOAD_DIR / "questions.jsonl") if q["variant"] == "seed"]
    by_doc = defaultdict(list)
    for q in seeds:
        by_doc[q["doc_id"]].append(q)
    trials = []
    for doc_id, own in by_doc.items():
        others = [q for q in seeds if q["doc_id"] != doc_id]
        for q in rng.sample(own, min(per_doc, len(own))):
            trials.append((doc_id, q["text"], "pdf"))
        for q in rng.sample(others, min(per_doc, len(others))):
            trials.append((doc_id, q["text"], "general"))

    out = {}
    for strategy in strategies:
        correct = defaultdict(list)
        for doc_id, text, expected in trials:
            result = retriever.search(text, doc_id, k=k, strategy=strategy)
            decision = retriever.decide(text, result, use_reranker=reranker.available())
            correct[expected].append(1.0 if decision.mode == expected else 0.0)
        out[strategy] = {"in_doc_pdf_rate": mean(correct["pdf"]),
                         "cross_doc_general_rate": mean(correct["general"]),
                         "accuracy": mean(correct["pdf"] + correct["general"]),
                         "n": len(trials)}
    return out


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--strategies", nargs="+",
                        default=["legacy", "dense", "bm25", "rrf", "dbsf"])
    parser.add_argument("--k", type=int, default=20)
    parser.add_argument("--seed", type=int, default=13)
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args(argv)

    bootstrap()
    results = run(args.strategies, args.k, args.seed, args.limit)
    results["provenance"] = provenance()
    path = write_json(run_dir("ir") / "ir_bench.json", results)
    for name, row in results["table"].items():
        allq = row["all"]
        print(f"{name:14s} R@3 {allq['r@3']['mean']:.3f}  MRR@10 {allq['mrr@10']['mean']:.3f}"
              f"  nDCG@10 {allq['ndcg@10']['mean']:.3f}  p50 "
              f"{row['latency_ms']['first_stage']['p50']:.1f} ms")
    print(f"[+] {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
