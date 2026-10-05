"""
Does question mining recover what the class asked about, and where?

    python -m eval.heatmap_bench

1. Simulate the class. Every ask in the session log is run through the production
   retriever (RRF + rerank) and written to the eval database's chat_turns exactly as the
   chat agent would write it -- mode, citations, the retrieval record, the student, the
   time. What is *not* simulated is the LLM: no reply is generated and nothing is judged,
   so the low-score and rejected signals are absent and the heatmap runs on volume,
   general-mode share and repeats alone. The known structure is kept per turn: which
   family (topic) and which page the question was written from.

2. Mine it with the production code: the MongoDB pipelines, MiniLM + HDBSCAN + c-TF-IDF,
   the confusion score, k-anonymity.

3. Score it against the known structure:
      clustering     NMI / ARI against question family, noise excluded and as singletons,
                     and the share of questions that were clustered at all
      attribution    the page a turn was attributed to vs the page its question came from
                     (exact and within one page)
      planted pages  recall of the two planted confusing pages among the top-3 by score
      cost           time per stage, and total time as the number of questions grows
"""

import argparse
import random
import sys
import time
from collections import Counter
from datetime import datetime, timedelta

from eval.common import WORKLOAD_DIR, bootstrap, provenance, read_jsonl, run_dir, write_json
from eval.metrics import mean, nmi_ari

SESSION_PREFIX = "sim-"


def _ms_key(when: datetime) -> str:
    """Millisecond, timezone-free: what a datetime looks like after a MongoDB round trip."""
    return when.replace(microsecond=(when.microsecond // 1000) * 1000,
                        tzinfo=None).isoformat()


def simulate(asks, questions):
    """Write the class's turns into chat_turns. Returns (user, time) -> gold labels."""
    from learnmate import config
    from learnmate.llm import rerank as reranker
    from learnmate.retrieval import retriever
    from learnmate.storage.ids import as_object_id
    from learnmate.storage.mongo import get_db

    turns = get_db()[config.COLL_CHAT_TURNS]
    turns.delete_many({"session_id": {"$regex": f"^{SESSION_PREFIX}"}})
    use_reranker = reranker.available()
    gold, rows = {}, []
    for ask in asks:
        q = questions[ask["qid"]]
        when = datetime.fromisoformat(ask["t"])
        when = when.replace(microsecond=(when.microsecond // 1000) * 1000)
        result = retriever.search(q["text"], q["doc_id"], k=retriever.candidate_k(use_reranker),
                                  strategy="rrf")
        decision = retriever.decide(q["text"], result, use_reranker)
        contexts = decision.contexts if decision.mode == "pdf" else []
        session = f"{SESSION_PREFIX}{ask['student']}-{ask['visit']}"
        meta = {
            "mode": decision.mode, "score": None, "accepted": None, "attempts": 0,
            "pages": [d.metadata.get("page_number") for d in contexts],
            "citations": [{"page": d.metadata.get("page_number"),
                           "paragraph": (d.metadata.get("chunk_index") or 0) + 1}
                          for d in contexts],
            "retrieval": retriever.summary(result, decision),
            "question": q["text"], "standalone_query": q["text"], "cache": None,
            "job_id": None,
        }
        doc_oid = as_object_id(q["doc_id"])
        rows.append({"session_id": session, "user_id": ask["student"], "role": "user",
                     "content": q["text"], "doc_id": doc_oid, "meta": {},
                     "created_at": when})
        rows.append({"session_id": session, "user_id": ask["student"], "role": "assistant",
                     "content": "[simulated reply]", "doc_id": doc_oid, "meta": meta,
                     "created_at": when + timedelta(milliseconds=1)})
        gold[(ask["student"], _ms_key(rows[-1]["created_at"]))] = {
            "family_id": ask["family_id"], "gold_page": q["gold_page"],
            "variant": ask["variant"], "mode": decision.mode}
    turns.insert_many(rows)
    return gold


def evaluate_document(doc_id, gold, planted):
    from learnmate import config
    from learnmate.insights import aggregate, service

    started = time.perf_counter()
    rows = aggregate.question_rows(doc_id)
    stats = aggregate.page_stats(doc_id, config.INSIGHTS_LOW_SCORE)
    aggregate_ms = (time.perf_counter() - started) * 1000
    result = service.compute_heatmap(doc_id, rows=rows, stats=stats)
    labels = result["_labels"]

    truth = []
    exact = near = attributed = 0
    for row in rows:
        created = row["created_at"]
        label = gold.get((row["user_id"], _ms_key(created)))
        truth.append(label["family_id"] if label else None)
        if label and row.get("page") is not None:
            attributed += 1
            exact += int(row["page"] == label["gold_page"])
            near += int(abs(row["page"] - label["gold_page"]) <= 1)
    keep = [i for i, t in enumerate(truth) if t is not None]
    families = [truth[i] for i in keep]
    predicted = [labels[i] for i in keep]

    shown = [p for p in result["pages"] if not p["suppressed"] and p["confusion"]]
    top = [p["page"] for p in sorted(shown, key=lambda p: -p["confusion"])[:3]]
    return {
        "doc_id": str(doc_id),
        "questions": len(rows),
        "clustering": nmi_ari(families, predicted),
        "clustering_noise_as_singletons": nmi_ari(families, predicted, noise_as_singletons=True),
        "clustered_share": result.get("clustered_share"),
        "topics_shown": len(result.get("topics") or []),
        "topics_suppressed": result.get("suppressed_topics"),
        "attribution_exact": exact / attributed if attributed else None,
        "attribution_within_1": near / attributed if attributed else None,
        "attributed_share": attributed / len(rows) if rows else None,
        "planted": planted, "top3": top,
        "planted_recall_at_3": (len(set(top) & set(planted)) / len(planted)) if planted else None,
        "pages_suppressed": sum(p["suppressed"] for p in result["pages"]),
        "timings": {**result["timings"], "aggregate_query_ms": aggregate_ms},
        "sample_topics": [{"terms": t["terms"], "size": t["size"], "pages": t["pages"]}
                          for t in (result.get("topics") or [])[:3]],
    }


def scaling(doc_ids, sizes, seed):
    """compute_heatmap time as the number of questions grows (rows resampled)."""
    from learnmate import config
    from learnmate.insights import aggregate, service

    rng = random.Random(seed)
    pool = []
    for doc_id in doc_ids:
        pool += aggregate.question_rows(doc_id)
    out = []
    for n in sizes:
        rows = sorted((rng.choice(pool) for _ in range(n)), key=lambda r: r["created_at"])
        pages = Counter(r.get("page") for r in rows if r.get("page") is not None)
        stats = {"pages": [{"page": p, "questions": c, "distinct_users": 10, "general": 0,
                            "judged": 0, "low": 0, "rejected": 0, "cache_hits": 0}
                           for p, c in pages.items()],
                 "totals": {"questions": n}}
        started = time.perf_counter()
        result = service.compute_heatmap("scaling", rows=rows, stats=stats, n_pages=20)
        out.append({"questions": n, "total_ms": (time.perf_counter() - started) * 1000,
                    **{k: v for k, v in result["timings"].items() if k != "total_ms"}})
        print(f"  {n} questions: {out[-1]['total_ms']:.0f} ms")
    return out


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--sizes", nargs="+", type=int, default=[100, 250, 500, 1000, 2000])
    parser.add_argument("--seed", type=int, default=13)
    args = parser.parse_args(argv)

    bootstrap()
    import json

    manifest = json.loads((WORKLOAD_DIR / "manifest.json").read_text(encoding="utf-8"))
    questions = {q["qid"]: q for q in read_jsonl(WORKLOAD_DIR / "questions.jsonl")}
    asks = read_jsonl(WORKLOAD_DIR / "sessions.jsonl")

    started = time.perf_counter()
    gold = simulate(asks, questions)
    simulate_s = time.perf_counter() - started
    print(f"[*] simulated {len(asks)} turns in {simulate_s:.1f}s")

    per_doc = []
    for doc_id in sorted({ask["doc_id"] for ask in asks}):
        row = evaluate_document(doc_id, gold, manifest["planted_pages"].get(doc_id, []))
        per_doc.append(row)
        print(f"  {doc_id}: NMI {row['clustering']['nmi']:.3f} ARI {row['clustering']['ari']:.3f}"
              f" clustered {row['clustered_share']} attribution {row['attribution_exact']}")

    def avg(path):
        values = []
        for row in per_doc:
            value = row
            for key in path:
                value = value.get(key) if isinstance(value, dict) else None
            if isinstance(value, (int, float)):
                values.append(value)
        return mean(values)

    summary = {
        "nmi": avg(["clustering", "nmi"]), "ari": avg(["clustering", "ari"]),
        "nmi_noise_singletons": avg(["clustering_noise_as_singletons", "nmi"]),
        "ari_noise_singletons": avg(["clustering_noise_as_singletons", "ari"]),
        "clustered_share": avg(["clustered_share"]),
        "attribution_exact": avg(["attribution_exact"]),
        "attribution_within_1": avg(["attribution_within_1"]),
        "planted_recall_at_3": avg(["planted_recall_at_3"]),
        "general_mode_share": mean([1.0 if g["mode"] == "general" else 0.0
                                    for g in gold.values()]),
    }
    results = {"summary": summary, "documents": per_doc,
               "scaling": scaling(sorted({a["doc_id"] for a in asks}), args.sizes, args.seed),
               "turns": len(asks), "simulate_s": simulate_s, "provenance": provenance()}
    print(json.dumps(summary, indent=2))
    print(f"[+] {write_json(run_dir('insights') / 'heatmap_bench.json', results)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
