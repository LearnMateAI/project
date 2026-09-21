"""
Full chat turns through the real agent: how long a miss takes, how long a hit takes.

    python -m eval.chat_latency [--families 8] [--tau 0.xx]

For each sampled test family: ask its seed question (a cache miss -- the whole pipeline:
rewrite, retrieve, rerank, generate, judge, and a retry if the judge rejects), then one of
its paraphrases (a hit, if the first answer was accepted and the verifier agrees). Each
turn runs ChatAgent exactly as the API does, with persistence off so nothing is written to
a transcript. The cache collection is the eval one, emptied first.

Also recorded: the judge's pass rate on the misses, which cache_replay.py uses as the
realistic acceptance rate, and each turn's stage timings.

On the Windows laptop this is CPU inference (tens of seconds a miss); the paper's numbers
for the demo machine come from running the same script there.
"""

import argparse
import json
import random
import sys
import time
import uuid

from eval.common import RESULTS_DIR, WORKLOAD_DIR, bootstrap, provenance, read_jsonl, \
    run_dir, write_json
from eval.metrics import latency_summary


def _tau():
    path = RESULTS_DIR / "cache" / "cache_bench.json"
    if path.exists():
        return str(json.loads(path.read_text(encoding="utf-8"))["chosen"]["verified"]["tau"])
    return None


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--families", type=int, default=8)
    parser.add_argument("--tau", type=str, default=None)
    parser.add_argument("--seed", type=int, default=13)
    args = parser.parse_args(argv)

    tau = args.tau or _tau() or "0.90"
    bootstrap({"LEARNMATE_CACHE_ENABLED": "1", "LEARNMATE_CACHE_TAU": tau,
               "LEARNMATE_CACHE_COLLECTION": "eval_answer_cache_latency"})

    from learnmate.cache import get_answer_cache
    from learnmate.chat_agent import ChatAgent

    cache = get_answer_cache()
    if cache.client.collection_exists(cache.collection_name):
        cache.client.delete_collection(cache.collection_name)
    cache._ready = False

    questions = read_jsonl(WORKLOAD_DIR / "questions.jsonl")
    seeds = [q for q in questions if q["variant"] == "seed" and q["split"] == "test"]
    paras = {}
    for q in questions:
        if q["variant"] == "para":
            paras.setdefault(q["family_id"], []).append(q)
    rng = random.Random(args.seed)
    sample = rng.sample(seeds, min(args.families, len(seeds)))

    turns = []
    for q in sample:
        for kind, text in (("seed", q["text"]),
                           ("para", rng.choice(paras[q["family_id"]])["text"])):
            agent = ChatAgent(session_id=f"eval-{uuid.uuid4().hex[:8]}", doc_id=q["doc_id"],
                              verbose=False, persist=False)
            started = time.perf_counter()
            result = agent.ask(text)
            elapsed = (time.perf_counter() - started) * 1000
            cache_info = result.get("cache") or {}
            turns.append({"family_id": q["family_id"], "kind": kind, "ms": elapsed,
                          "hit": bool(cache_info.get("hit")),
                          "cache_reason": cache_info.get("reason"),
                          "mode": result.get("mode"),
                          "accepted": result.get("accepted"),
                          "score": (result.get("verdict") or {}).get("score"),
                          "attempts": len(result.get("attempts") or []),
                          "timings": result.get("timings")})
            print(f"  {kind:4s} {'HIT ' if turns[-1]['hit'] else 'miss'} "
                  f"{elapsed / 1000:6.1f}s  mode={result.get('mode')} "
                  f"score={turns[-1]['score']} accepted={result.get('accepted')}")

    misses = [t for t in turns if not t["hit"]]
    hits = [t for t in turns if t["hit"]]
    judged = [t for t in misses if t["mode"] == "pdf" and isinstance(t["score"], int)]
    results = {
        "tau": float(tau),
        "turns": turns,
        "miss_ms": latency_summary([t["ms"] for t in misses]),
        "hit_ms": latency_summary([t["ms"] for t in hits]),
        "paraphrase_hit_rate": (sum(t["hit"] for t in turns if t["kind"] == "para")
                                / max(1, sum(t["kind"] == "para" for t in turns))),
        "judge_pass_rate": (sum(bool(t["accepted"]) for t in judged) / len(judged)
                            if judged else None),
        "provenance": provenance(hash_models=True),
    }
    print(f"miss p50 {results['miss_ms']['p50']}, hit p50 {results['hit_ms']['p50']}")
    print(f"[+] {write_json(run_dir('cache') / 'chat_latency.json', results)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
