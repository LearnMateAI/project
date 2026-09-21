"""
Replay a fortnight of a class's questions through the answer cache, in time order.

    python -m eval.cache_replay [--tau 0.xx] [--accept-rate 1.0 0.6]

The session log (eval/workload.py sessions) is 40 students asking about their chapters.
Each ask is looked up in a cache that starts empty; a miss is answered by the full
pipeline and, if the judge accepts it, stored. Whether the judge accepts is the one thing
this replay cannot run for every ask (that is the LLM), so it is a parameter: 1.0, and the
pass rate actually measured in chat_latency.py when that result exists.

Reported per acceptance rate: the hit rate overall and as the class goes on (a cold cache
fills), and hit precision -- the share of reuses whose cached question was the same family
as the ask. Expected turn latency then follows from the measured hit and miss latencies.
"""

import argparse
import json
import random
import sys

from eval.common import RESULTS_DIR, WORKLOAD_DIR, bootstrap, provenance, read_jsonl, \
    run_dir, write_json

COLLECTION = "eval_answer_cache_replay"


def _default_tau():
    path = RESULTS_DIR / "cache" / "cache_bench.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))["chosen"]["verified"]["tau"]
    return None


def _measured_accept_rate():
    path = RESULTS_DIR / "cache" / "chat_latency.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8")).get("judge_pass_rate")
    return None


def replay(asks, questions, tau, accept_rate, seed):
    from learnmate.cache.answer_cache import AnswerCache

    rng = random.Random(seed)
    cache = AnswerCache(collection_name=COLLECTION)
    if cache.client.collection_exists(COLLECTION):
        cache.client.delete_collection(COLLECTION)
    family_of_entry = {}
    curve, hits, correct = [], 0, 0
    for index, ask in enumerate(asks, start=1):
        q = questions[ask["qid"]]
        vector = cache.embeddings.embed_query(q["text"])
        result = cache.lookup(q["doc_id"], q["text"], query_vector=vector, tau=tau,
                              use_verifier=True, log=False)
        if result.hit:
            hits += 1
            # A near-miss question is never answered by its family's entry correctly.
            same = (family_of_entry.get(result.entry_id) == ask["family_id"]
                    and ask["variant"] != "neg")
            correct += int(same)
        elif rng.random() < accept_rate:
            entry = cache.store(q["doc_id"], q["text"], "[answer]", contexts=[],
                                judge_score=90, query_vector=vector)
            family_of_entry[entry] = ask["family_id"] if ask["variant"] != "neg" \
                else f"{ask['family_id']}/neg"
        if index % 20 == 0 or index == len(asks):
            curve.append({"asks": index, "hit_rate": hits / index})
    cache.client.delete_collection(COLLECTION)
    return {"accept_rate": accept_rate, "tau": tau, "asks": len(asks), "hits": hits,
            "hit_rate": hits / len(asks) if asks else 0.0,
            "hit_precision": correct / hits if hits else None,
            "entries": len(family_of_entry), "curve": curve}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--tau", type=float, default=None)
    parser.add_argument("--accept-rate", type=float, nargs="*", default=None)
    parser.add_argument("--seed", type=int, default=13)
    args = parser.parse_args(argv)

    bootstrap()
    tau = args.tau or _default_tau()
    if tau is None:
        raise SystemExit("Run eval.cache_bench first, or pass --tau.")
    rates = args.accept_rate or sorted({1.0, *filter(None, [_measured_accept_rate()])})
    questions = {q["qid"]: q for q in read_jsonl(WORKLOAD_DIR / "questions.jsonl")}
    asks = read_jsonl(WORKLOAD_DIR / "sessions.jsonl")
    runs = [replay(asks, questions, tau, rate, args.seed) for rate in rates]
    for run in runs:
        print(f"accept {run['accept_rate']:.2f}: hit rate {run['hit_rate']:.3f}, "
              f"hit precision {run['hit_precision']}")
    path = write_json(run_dir("cache") / "cache_replay.json",
                      {"runs": runs, "provenance": provenance()})
    print(f"[+] {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
