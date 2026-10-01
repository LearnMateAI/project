"""
Base vs fine-tuned comparison on the lm-legal-v0.1 held-out splits.

    python run_eval.py generate --model base
    python run_eval.py generate --model finetuned
    python run_eval.py score

Both models see the same sampled items, the same system prompt, the same decoding
settings and the same hardware. Generation is resumable: rows already present in
predictions/<model>_<split>.jsonl are skipped.

Scoring mirrors model-Thevindu/03_testing_and_versioning/evaluate_candidate.ipynb:
  accuracy           fraction of items with token-F1 >= 0.50 vs the gold turn
  groundedness       validate_pairs.check_pair (same checker as the registry rescore)
  hallucination_rate 1 - groundedness
  latency_p95_ms     p95 of end-to-end generation time per item
"""
from __future__ import annotations

import argparse
import json
import os
import random
import re
import statistics
import sys
import time
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "model-Thevindu" / "01_dataset_pipeline"))
from validate_pairs import check_pair  # noqa: E402

MODELS_DIR = ROOT / "integrated-backend" / "models"
MODELS = {
    "base": MODELS_DIR / "qwen2.5-3b-instruct-q4_k_m.gguf",
    "finetuned": MODELS_DIR / "learnmate-legal-qwen2.5-1.5b-q8_0.gguf",
}
LABELS = {
    "base": "Qwen2.5-3B-Instruct (base, q4_k_m)",
    "finetuned": "Qwen2.5-1.5B + LoRA qwen25-lora-20260815-090709 (merged, q8_0)",
}
SPLITS = {
    "test": "chapter-held-out",
    "test_strict": "document-held-out",
}
PRED_DIR = HERE / "predictions"

PER_TYPE = 30          # items per pair_type per split -> 60 per split
SEED = 42
MAX_NEW_TOKENS = 256   # same cap as the Colab eval
TEMPERATURE = 0.0      # greedy, so reruns reproduce
F1_PASS = 0.50         # acceptance_thresholds.yaml f1_pass_threshold
N_CTX = 4096


def load_split(split: str) -> list[dict]:
    with (HERE / f"{split}.jsonl").open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def sample(split: str) -> list[dict]:
    rows = load_split(split)
    rng = random.Random(SEED)
    out: list[dict] = []
    for ptype in sorted({r["pair_type"] for r in rows}):
        group = sorted((r for r in rows if r["pair_type"] == ptype), key=lambda r: r["pair_id"])
        out += rng.sample(group, min(PER_TYPE, len(group)))
    return out


def turn(row: dict, role: str) -> str:
    return next(m["content"] for m in row["messages"] if m["role"] == role)


def source_of(row: dict) -> str:
    user = turn(row, "user")
    return user.split("---SOURCE EXCERPT---")[-1].strip() if "---SOURCE EXCERPT---" in user else user


def generate(model_key: str) -> None:
    from llama_cpp import Llama

    llm = Llama(
        model_path=str(MODELS[model_key]),
        n_ctx=N_CTX,
        n_threads=int(os.environ.get("EVAL_THREADS", "6")),
        seed=SEED,
        verbose=False,
    )
    PRED_DIR.mkdir(exist_ok=True)
    # One untimed warm-up so the first timed item doesn't pay for page-in.
    llm.create_chat_completion(messages=[{"role": "user", "content": "Hi"}], max_tokens=8)

    for split in SPLITS:
        out_path = PRED_DIR / f"{model_key}_{split}.jsonl"
        done = set()
        if out_path.exists():
            done = {json.loads(l)["pair_id"] for l in out_path.read_text(encoding="utf-8").splitlines() if l.strip()}
        items = sample(split)
        with out_path.open("a", encoding="utf-8") as f:
            for i, row in enumerate(items, 1):
                if row["pair_id"] in done:
                    continue
                messages = [m for m in row["messages"] if m["role"] in ("system", "user")]
                t0 = time.perf_counter()
                resp = llm.create_chat_completion(
                    messages=messages, max_tokens=MAX_NEW_TOKENS, temperature=TEMPERATURE,
                )
                ms = (time.perf_counter() - t0) * 1000
                text = (resp["choices"][0]["message"]["content"] or "").strip()
                f.write(json.dumps({
                    "pair_id": row["pair_id"],
                    "pair_type": row["pair_type"],
                    "prediction": text,
                    "latency_ms": round(ms, 1),
                    "completion_tokens": resp["usage"]["completion_tokens"],
                }, ensure_ascii=False) + "\n")
                f.flush()
                print(f"[{model_key}] {split} {i}/{len(items)} {ms:.0f} ms", flush=True)


def tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def token_f1(pred: str, gold: str) -> float:
    p, g = tokenize(pred), tokenize(gold)
    if not p and not g:
        return 1.0
    if not p or not g:
        return 0.0
    overlap = sum((Counter(p) & Counter(g)).values())
    if overlap == 0:
        return 0.0
    precision, recall = overlap / len(p), overlap / len(g)
    return 2 * precision * recall / (precision + recall)


def rouge_l(pred: str, gold: str) -> float:
    """ROUGE-L F1: longest common subsequence of tokens, so word order counts."""
    p, g = tokenize(pred), tokenize(gold)
    if not p or not g:
        return 0.0
    prev = [0] * (len(g) + 1)
    for pt in p:
        cur = [0]
        for j, gt in enumerate(g, 1):
            cur.append(prev[j - 1] + 1 if pt == gt else max(prev[j], cur[j - 1]))
        prev = cur
    lcs = prev[-1]
    if lcs == 0:
        return 0.0
    precision, recall = lcs / len(p), lcs / len(g)
    return 2 * precision * recall / (precision + recall)


_EMBEDDER = None


def semantic_similarity(pairs: list[tuple[str, str]]) -> list[float]:
    """Cosine similarity of prediction vs gold with the backend's own embedder
    (all-MiniLM-L6-v2), so a correct answer in different words still scores."""
    global _EMBEDDER
    from sentence_transformers import SentenceTransformer

    if _EMBEDDER is None:
        _EMBEDDER = SentenceTransformer("all-MiniLM-L6-v2")
    preds = _EMBEDDER.encode([p for p, _ in pairs], normalize_embeddings=True)
    golds = _EMBEDDER.encode([g for _, g in pairs], normalize_embeddings=True)
    return [float((a * b).sum()) for a, b in zip(preds, golds)]


def p95(values: list[float]) -> float:
    s = sorted(values)
    k = (len(s) - 1) * 0.95
    lo, hi = int(k), min(int(k) + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (k - lo)


def score() -> None:
    results = []
    for split, split_name in SPLITS.items():
        rows = {r["pair_id"]: r for r in load_split(split)}
        for model_key in MODELS:
            path = PRED_DIR / f"{model_key}_{split}.jsonl"
            if not path.exists():
                continue
            preds = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
            correct = grounded = 0
            f1s, rls, lat = [], [], []
            sims = semantic_similarity([(p["prediction"], turn(rows[p["pair_id"]], "assistant")) for p in preds])
            for p in preds:
                row = rows[p["pair_id"]]
                f1 = token_f1(p["prediction"], turn(row, "assistant"))
                f1s.append(f1)
                rls.append(rouge_l(p["prediction"], turn(row, "assistant")))
                correct += f1 >= F1_PASS
                allow = {row["section_id"]} if row.get("section_id") else None
                ok, _ = check_pair({"output": p["prediction"], "input": source_of(row)}, allow=allow)
                grounded += ok
                lat.append(p["latency_ms"])
            n = len(preds)
            results.append({
                "split": split, "split_name": split_name, "model": model_key, "label": LABELS[model_key],
                "n": n,
                "accuracy": round(correct / n, 4),
                "mean_token_f1": round(statistics.mean(f1s), 4),
                "rouge_l": round(statistics.mean(rls), 4),
                "semantic_similarity": round(statistics.mean(sims), 4),
                "groundedness": round(grounded / n, 4),
                "hallucination_rate": round(1 - grounded / n, 4),
                "latency_p95_ms": round(p95(lat), 1),
                "latency_median_ms": round(statistics.median(lat), 1),
            })
    (HERE / "results.json").write_text(json.dumps(results, indent=2), encoding="utf-8")

    print(f"{'split':<20}{'model':<11}{'n':>4}{'acc':>8}{'meanF1':>8}{'rougeL':>8}{'semsim':>8}"
          f"{'ground':>8}{'halluc':>8}{'p95 ms':>10}")
    for r in results:
        print(f"{r['split_name']:<20}{r['model']:<11}{r['n']:>4}{r['accuracy']:>8.3f}{r['mean_token_f1']:>8.3f}"
              f"{r['rouge_l']:>8.3f}{r['semantic_similarity']:>8.3f}"
              f"{r['groundedness']:>8.3f}{r['hallucination_rate']:>8.3f}{r['latency_p95_ms']:>10.0f}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("generate")
    g.add_argument("--model", choices=list(MODELS), required=True)
    sub.add_parser("score")
    args = ap.parse_args()
    generate(args.model) if args.cmd == "generate" else score()
