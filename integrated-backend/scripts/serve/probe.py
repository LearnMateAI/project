"""
Check a llama-server before trusting it with the job queue, and measure what its slots buy.

    python scripts/serve/probe.py                       # both servers from .env / defaults
    python scripts/serve/probe.py --out data/eval_results/serving_probe.json

Four checks per server:

    health      /health answers
    props       how many parallel slots it was started with
    schema      the judge's verdict JSON schema, 10 times: every reply must parse. This is
                the grammar the in-process backend enforced; if the server ignored it, the
                judge's scores would silently become parse failures.
    batching    the same short generation sent 1, 2, 4, ... slots-at-a-time. Aggregate
                tokens/second should rise with concurrency; that rise is continuous
                batching, and it is the whole case for the worker pool.
"""

import argparse
import concurrent.futures as futures
import json
import sys
import time
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from learnmate import config  # noqa: E402
from learnmate.evaluator.verdict import VERDICT_SCHEMA  # noqa: E402

PROMPT = [{"role": "user", "content":
           "In three sentences, explain what a fiduciary duty is to a first-year student."}]


def _root(api_url: str) -> str:
    return api_url.rstrip("/").removesuffix("/v1")


def _chat(api_url: str, model: str, max_tokens: int, schema=None, timeout=300):
    body = {"model": model, "messages": PROMPT, "max_tokens": max_tokens,
            "temperature": 0.0}
    if schema is not None:
        body["messages"] = [{"role": "user", "content":
                             "Score this answer from 1 to 100 and explain in one sentence: "
                             "'A fiduciary must act in the beneficiary's interest.'"}]
        body["response_format"] = {"type": "json_schema",
                                   "json_schema": {"name": "verdict", "schema": schema,
                                                   "strict": True}}
    started = time.perf_counter()
    response = requests.post(f"{api_url.rstrip('/')}/chat/completions", json=body,
                             timeout=timeout)
    response.raise_for_status()
    data = response.json()
    elapsed = time.perf_counter() - started
    tokens = (data.get("usage") or {}).get("completion_tokens") or 0
    if schema is not None:
        return (data["choices"][0]["message"]["content"], tokens, elapsed,
                data["choices"][0].get("finish_reason"))
    return data["choices"][0]["message"]["content"], tokens, elapsed


def probe(name: str, api_url: str, model: str, max_slots: int, tokens: int) -> dict:
    report = {"server": name, "api_url": api_url, "model": model}
    root = _root(api_url)
    try:
        report["health"] = requests.get(f"{root}/health", timeout=5).status_code == 200
    except requests.RequestException as exc:
        report["health"] = False
        report["error"] = str(exc)
        return report
    try:
        props = requests.get(f"{root}/props", timeout=5).json()
        report["total_slots"] = props.get("total_slots")
        report["model_path"] = props.get("model_path")
    except Exception:
        report["total_slots"] = None

    # 512 tokens, as the judge is called with (llm/registry.get_judge_llm). A reply cut off
    # by the token limit is invalid JSON however well the grammar held, so truncations are
    # counted apart from genuine schema failures.
    parsed = truncated = 0
    for _ in range(10):
        text, _, _, finish = _chat(api_url, model, 512, schema=VERDICT_SCHEMA)
        try:
            verdict = json.loads(text)
            parsed += int(isinstance(verdict.get("score"), int))
        except ValueError:
            truncated += int(finish == "length")
    report["schema_parse_rate"] = parsed / 10
    report["schema_truncated"] = truncated

    slots = report.get("total_slots") or max_slots
    levels, level = [], 1
    while level <= max(1, min(slots, max_slots)):
        levels.append(level)
        level *= 2
    batching = []
    for concurrency in levels:
        started = time.perf_counter()
        with futures.ThreadPoolExecutor(concurrency) as pool:
            results = list(pool.map(lambda _: _chat(api_url, model, tokens),
                                    range(concurrency)))
        wall = time.perf_counter() - started
        generated = sum(r[1] for r in results)
        batching.append({"concurrency": concurrency, "wall_s": round(wall, 3),
                         "tokens": generated,
                         "aggregate_tok_s": round(generated / wall, 2) if wall else None,
                         "mean_request_s": round(sum(r[2] for r in results) / concurrency, 3)})
        print(f"  {name}: {concurrency} concurrent -> {batching[-1]['aggregate_tok_s']} tok/s")
    report["batching"] = batching
    return report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--generator-url", default=config.GENERATOR_API_URL)
    parser.add_argument("--generator-model", default="qwen25-3b")
    parser.add_argument("--judge-url", default=config.JUDGE_API_URL)
    parser.add_argument("--judge-model", default="llama32-3b-judge")
    parser.add_argument("--max-slots", type=int, default=8)
    parser.add_argument("--tokens", type=int, default=96)
    parser.add_argument("--out", default=None)
    args = parser.parse_args(argv)

    reports = [
        probe("generator", args.generator_url, args.generator_model, args.max_slots,
              args.tokens),
        probe("judge", args.judge_url, args.judge_model, args.max_slots, args.tokens),
    ]
    print(json.dumps(reports, indent=2))
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(reports, indent=2), encoding="utf-8")
    ok = all(r.get("health") and r.get("schema_parse_rate", 0) >= 0.9 for r in reports)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
