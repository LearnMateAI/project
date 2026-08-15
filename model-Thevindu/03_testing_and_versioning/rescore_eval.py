"""Re-score saved eval_predictions with the Stage-2 citation checker.

Does not load the adapter. Joins predictions back to processed_v01 test JSONL
for the source excerpt. Optionally runs an LLM-as-judge for accuracy (same
CHAT_GROUNDED idea as the live Verification Agent).

  python rescore_eval.py
  python rescore_eval.py --llm-judge   # needs OPENAI_API_KEY in a gitignored .env
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PIPE = ROOT / "01_dataset_pipeline"
sys.path.insert(0, str(PIPE))

from dotenv import load_dotenv  # noqa: E402
from validate_pairs import check_pair  # noqa: E402

HERE = Path(__file__).resolve().parent
PRED = HERE / "eval_predictions"
DATA = PIPE / "processed_v01"
THRESH = HERE / "acceptance_thresholds.yaml"
REGISTRY = HERE / "version_registry.csv"

RUN_ID = "qwen25-lora-20260815-090709"
SPLITS = (
    ("test", "in_corpus_accuracy (chapter-held-out)"),
    ("test_strict", "accuracy (document-held-out)"),
)

JUDGE_PROMPT = """You grade a study-assistant answer against a gold answer AND a source excerpt.
The live product treats any claim not supported by retrieved context as a hallucination.
Score CORRECT only if the candidate is substantively right according to the gold/excerpt
and does not invent section numbers, facts, or holdings absent from the excerpt.
Return JSON: {"correct": true or false, "reason": "one sentence"}."""


def load_sources(split: str) -> dict[str, dict]:
    out: dict[str, dict] = {}
    with (DATA / f"{split}.jsonl").open(encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            r = json.loads(line)
            user = next(m["content"] for m in r["messages"] if m["role"] == "user")
            gold = next(m["content"] for m in r["messages"] if m["role"] == "assistant")
            source = (
                user.split("---SOURCE EXCERPT---")[-1].strip()
                if "---SOURCE EXCERPT---" in user
                else user
            )
            out[r["pair_id"]] = {
                "source": source,
                "gold": gold,
                "section_id": r.get("section_id"),
                "pair_type": r["pair_type"],
            }
    return out


def grounded(pred: str, src: dict) -> bool:
    pair = {"output": pred, "input": src.get("source") or ""}
    allow = {src["section_id"]} if src.get("section_id") else None
    ok, _ = check_pair(pair, allow=allow)
    return ok


def append_registry(row: dict) -> None:
    fieldnames = [
        "candidate_id", "run_id", "base_model", "dataset_version", "evaluated_at_utc",
        "eval_split", "metric_definition",
        "accuracy", "groundedness", "hallucination_rate", "latency_p95_ms",
        "fallback_model", "fallback_accuracy", "fallback_groundedness",
        "passed", "fail_reasons", "notes",
    ]
    text = REGISTRY.read_text(encoding="utf-8") if REGISTRY.exists() else ""
    with REGISTRY.open("a", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        if text.strip() == "":
            w.writeheader()
        w.writerow(row)


def llm_correct(client, model: str, gold: str, pred: str, source: str) -> bool:
    resp = client.chat.completions.create(
        model=model,
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": JUDGE_PROMPT},
            {
                "role": "user",
                "content": (
                    f"SOURCE EXCERPT:\n{source[:4000]}\n\n"
                    f"GOLD:\n{gold[:1500]}\n\nCANDIDATE:\n{pred[:1500]}"
                ),
            },
        ],
    )
    raw = resp.choices[0].message.content or "{}"
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return False
    return bool(parsed.get("correct"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--llm-judge", action="store_true")
    args = parser.parse_args()

    load_dotenv(PIPE / ".env")
    import yaml

    thresholds = yaml.safe_load(THRESH.read_text(encoding="utf-8"))
    m = thresholds["metrics"]

    judge_client = None
    judge_model = None
    if args.llm_judge:
        from openai import OpenAI

        key = os.getenv("OPENAI_API_KEY")
        if not key:
            print("FAIL: --llm-judge needs OPENAI_API_KEY in the gitignored .env", file=sys.stderr)
            return 1
        judge_client = OpenAI(api_key=key)
        judge_model = os.getenv("OPENAI_MODEL") or "gpt-4o-mini"
        print(f"LLM-as-judge on (model name only): {judge_model}")

    existing = {
        r["eval_split"]: r
        for r in csv.DictReader(REGISTRY.open(encoding="utf-8"))
        if r.get("run_id") == RUN_ID and r.get("notes") != "dry_run"
    }

    for split, metric_name in SPLITS:
        srcs = load_sources(split)
        preds = [
            json.loads(l)
            for l in (PRED / f"{RUN_ID}_{split}.jsonl").read_text(encoding="utf-8").splitlines()
            if l.strip()
        ]
        n = len(preds)
        ungrounded = 0
        correct = 0
        latencies = []
        for p in preds:
            s = srcs.get(p["pair_id"], {})
            cand = p.get("candidate") or ""
            if not grounded(cand, s):
                ungrounded += 1
            latencies.append(float(p.get("candidate_ms") or 0))
            if args.llm_judge:
                correct += int(
                    llm_correct(judge_client, judge_model, s.get("gold") or p.get("gold") or "",
                                cand, s.get("source") or "")
                )
            else:
                # Keep the original token-F1 accuracy from the Colab registry row.
                pass
        hall = ungrounded / n
        ground = 1.0 - hall
        p95 = sorted(latencies)[max(0, int(0.95 * (n - 1)))] if latencies else float("nan")
        prev = existing.get(split, {})
        acc = (correct / n) if args.llm_judge else float(prev.get("accuracy") or 0)
        fb_acc = float(prev.get("fallback_accuracy") or 0)
        fb_ground = float(prev.get("fallback_groundedness") or 0)

        reasons = []
        if acc < m["accuracy"]["minimum"]:
            reasons.append(f"accuracy {acc:.3f} < {m['accuracy']['minimum']}")
        if ground < m["groundedness"]["minimum"]:
            reasons.append(f"groundedness {ground:.3f} < {m['groundedness']['minimum']}")
        if hall > m["hallucination_rate"]["maximum"]:
            reasons.append(f"hallucination_rate {hall:.3f} > {m['hallucination_rate']['maximum']}")
        if p95 > m["latency_p95_ms"]["maximum_ms"]:
            reasons.append(
                f"latency_p95_ms {p95:.0f} > {m['latency_p95_ms']['maximum_ms']} "
                f"(eval_hardware={m['latency_p95_ms'].get('eval_hardware')})"
            )
        slack = m["fallback_comparison"]["accuracy_slack"]
        ok_fb = acc >= fb_acc or (ground >= fb_ground and acc >= fb_acc - slack)
        if not ok_fb:
            reasons.append(
                f"failed fallback comparison (cand_acc={acc:.3f}, fb_acc={fb_acc:.3f}, "
                f"cand_ground={ground:.3f}, fb_ground={fb_ground:.3f})"
            )
        passed = len(reasons) == 0
        grader = f"llm_judge:{judge_model}" if args.llm_judge else "token-F1 from original Colab row"
        notes = (
            f"rescored groundedness with validate_pairs.py; accuracy={grader}; "
            "latency still Colab T4 sequential 4-bit, not production hardware"
        )
        print(f"\n{split}  n={n}  acc={acc:.4f}  ground={ground:.4f}  hall={hall:.4f}  p95={p95:.0f}ms")
        print("PASSED" if passed else "FAILED")
        for r in reasons:
            print(" -", r)

        append_registry({
            "candidate_id": RUN_ID,
            "run_id": RUN_ID,
            "base_model": "Qwen/Qwen2.5-1.5B-Instruct",
            "dataset_version": "lm-legal-v0.1",
            "evaluated_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            "eval_split": split,
            "metric_definition": metric_name,
            "accuracy": f"{acc:.4f}",
            "groundedness": f"{ground:.4f}",
            "hallucination_rate": f"{hall:.4f}",
            "latency_p95_ms": f"{p95:.1f}",
            "fallback_model": prev.get("fallback_model", "gpt-4o-mini"),
            "fallback_accuracy": f"{fb_acc:.4f}",
            "fallback_groundedness": f"{fb_ground:.4f}",
            "passed": str(passed),
            "fail_reasons": " | ".join(reasons),
            "notes": notes,
        })

    print("\nwrote", REGISTRY)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
