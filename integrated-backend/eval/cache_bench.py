"""
Answer-cache decisions: how often a reuse is right, and how often it is available.

    python -m eval.cache_bench

Setup. The cache is filled with one entry per question family -- its seed question -- as
if one student had asked each and had an accepted answer. Then it is probed with:

    paraphrases   another student asking the same thing in other words: the right result
                  is a hit on *that family's* entry (a hit on another family's is wrong)
    near-misses   a different question on the same topic ("...an exception to...",
                  "...the opposite case..."): the right result is a miss

Each probe's nearest cached questions and their cosine similarities are computed once, and
the duplicate-question verifier's score for each; the hit rule (learnmate/cache.decide) is
then replayed offline across every threshold, with and without the verifier. So the sweep
measures exactly the production rule, not an approximation of it.

Reported: precision of hits (a wrong reuse is the harm), recall over paraphrases (a reuse
missed is only a slower answer), F1, and the false-hit rate on near-misses. Thresholds are
chosen on the development chapter and reported on the other seven. Lookup latency is the
real `AnswerCache.lookup` path, end to end.
"""

import argparse
import sys
import time
from collections import defaultdict

from eval.common import WORKLOAD_DIR, bootstrap, provenance, read_jsonl, run_dir, write_json
from eval.metrics import latency_summary, prf1

COLLECTION = "eval_answer_cache_bench"
TAUS = [round(0.60 + 0.02 * i, 2) for i in range(20)]         # 0.60 .. 0.98
# Wide, and low as well as high: the Quora-trained verifier is conservative -- a true
# paraphrase can score 0.2-0.3 while a near-miss scores ~0.02 -- so the useful threshold
# may sit well under its nominal 0.5.
VERIFIER_THRESHOLDS = [0.05, 0.1, 0.2, 0.3, 0.5, 0.7]


def _evaluate(probes, tau, v_thr, use_verifier):
    from learnmate.cache import decide

    tp = fp = fn = neg_hits = negatives = 0
    for probe in probes:
        sims = [c["sim"] for c in probe["candidates"]]
        vs = None if probe["verifier"] is None else probe["verifier"]
        hit, index, _ = decide(sims, vs, tau, v_thr, use_verifier)
        if probe["variant"] == "para":
            if hit and probe["candidates"][index]["family_id"] == probe["family_id"]:
                tp += 1
            elif hit:
                fp += 1
            else:
                fn += 1
        else:
            negatives += 1
            if hit:
                fp += 1
                neg_hits += 1
    scores = prf1(tp, fp, fn)
    scores.update({"tp": tp, "fp": fp, "fn": fn,
                   "false_hit_rate_neg": neg_hits / negatives if negatives else 0.0})
    return scores


def _sweep(probes):
    rows = []
    for tau in TAUS:
        rows.append({"tau": tau, "verifier": None, **_evaluate(probes, tau, 0.0, False)})
        for v_thr in VERIFIER_THRESHOLDS:
            rows.append({"tau": tau, "verifier": v_thr,
                         **_evaluate(probes, tau, v_thr, True)})
    return rows


def _best(rows, verified: bool):
    pool = [row for row in rows if (row["verifier"] is not None) == verified]
    return max(pool, key=lambda row: (row["f1"], row["precision"], -row["tau"]))


def run(candidates_n: int, latency_samples: int):
    from learnmate import config
    from learnmate.cache.answer_cache import AnswerCache, model_key
    from learnmate.llm import equivalence

    questions = read_jsonl(WORKLOAD_DIR / "questions.jsonl")
    seeds = [q for q in questions if q["variant"] == "seed"]
    probes_src = [q for q in questions if q["variant"] in ("para", "neg")]

    cache = AnswerCache(collection_name=COLLECTION)
    if cache.client.collection_exists(COLLECTION):
        cache.client.delete_collection(COLLECTION)
    family_of = {}
    started = time.perf_counter()
    for q in seeds:
        entry = cache.store(q["doc_id"], q["text"], f"[answer for {q['family_id']}]",
                            contexts=[], judge_score=90)
        family_of[entry] = q["family_id"]
    store_ms = (time.perf_counter() - started) * 1000 / max(1, len(seeds))
    print(f"[*] cached {len(seeds)} seed questions")

    if not equivalence.available():
        raise SystemExit("The question verifier could not be loaded.")

    probes = []
    for q in probes_src:
        info = cache._doc_info(q["doc_id"])
        vector = cache.embeddings.embed_query(q["text"])
        response = cache.client.query_points(
            collection_name=COLLECTION, query=vector,
            query_filter=cache._filter(q["doc_id"], info, model_key()),
            limit=candidates_n, with_payload=True)
        candidates = [{"family_id": family_of.get(str(p.id)), "sim": float(p.score),
                       "text": (p.payload or {}).get("query_text", "")}
                      for p in response.points]
        verifier = equivalence.score_pairs([(q["text"], c["text"]) for c in candidates])
        probes.append({"qid": q["qid"], "family_id": q["family_id"], "variant": q["variant"],
                       "split": q["split"], "candidates": candidates, "verifier": verifier})

    dev = [p for p in probes if p["split"] == "dev"]
    test = [p for p in probes if p["split"] == "test"]
    dev_rows, test_rows = _sweep(dev), _sweep(test)

    chosen = {}
    for label, verified in (("embedding_only", False), ("verified", True)):
        best = _best(dev_rows, verified)
        at_test = next(row for row in test_rows
                       if row["tau"] == best["tau"] and row["verifier"] == best["verifier"])
        chosen[label] = {"tau": best["tau"], "verifier_threshold": best["verifier"],
                         "dev": best, "test": at_test}

    # What an embedding threshold alone must give up to be as safe as the verified cache:
    # the best recall among thresholds whose test precision is at least as high.
    target = chosen["verified"]["test"]["precision"]
    safe = [row for row in test_rows if row["verifier"] is None and row["precision"] >= target]
    chosen["embedding_only_matched_precision"] = (
        max(safe, key=lambda row: row["recall"]) if safe else None)

    # Real lookups, end to end, at the chosen setting.
    lookup = []
    for probe in probes_src[:latency_samples]:
        started = time.perf_counter()
        cache.lookup(probe["doc_id"], probe["text"], tau=chosen["verified"]["tau"],
                     use_verifier=True, log=False)
        lookup.append((time.perf_counter() - started) * 1000)

    by_variant = defaultdict(int)
    for p in probes:
        by_variant[f"{p['split']}:{p['variant']}"] += 1
    cache.client.delete_collection(COLLECTION)
    return {"chosen": chosen, "sweep": {"dev": dev_rows, "test": test_rows},
            "probes": dict(by_variant), "cached_entries": len(seeds),
            "candidates": candidates_n, "verifier_model": config.CACHE_VERIFIER_MODEL,
            "embedding_model": config.EMBEDDING_MODEL,
            "latency_ms": {"lookup": latency_summary(lookup), "store_mean": store_ms}}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--candidates", type=int, default=3)
    parser.add_argument("--latency-samples", type=int, default=100)
    args = parser.parse_args(argv)

    bootstrap()
    results = run(args.candidates, args.latency_samples)
    results["provenance"] = provenance()
    for label in ("embedding_only", "verified"):
        row = results["chosen"][label]
        test = row["test"]
        print(f"{label:15s} tau={row['tau']} v={row['verifier_threshold']}  test P "
              f"{test['precision']:.3f} R {test['recall']:.3f} F1 {test['f1']:.3f} "
              f"false-hit(neg) {test['false_hit_rate_neg']:.3f}")
    print(f"lookup p50 {results['latency_ms']['lookup']['p50']:.1f} ms")
    print(f"[+] {write_json(run_dir('cache') / 'cache_bench.json', results)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
