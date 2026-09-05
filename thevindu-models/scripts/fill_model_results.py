"""Copy hub scores into each model's RESULTS.md and version_registry.csv."""

from __future__ import annotations

import json
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent
GGUF = json.loads((HUB / "results" / "gguf.json").read_text(encoding="utf-8"))
REAL = json.loads((HUB / "results" / "real_pdf.json").read_text(encoding="utf-8"))


def write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def gen_row(mid: str) -> dict:
    return next(r for r in GGUF["generators"] if r["id"] == mid)


def judge_row(mid: str) -> dict:
    return next(r for r in GGUF["judges"] if r["id"] == mid)


def fill_generator(folder: str, mid: str, name: str, verdict: str, sentence: str) -> None:
    row = gen_row(mid)
    g = f"{row['grounded_hit_rate']:.2f}"
    j = f"{row['json_valid_rate']:.2f}"
    ms = int(round(row["mean_ms"]))
    write(HUB / folder / "RESULTS.md", f"""# RESULTS — {name}

**Machine:** Windows AMD64 Intel Family 6 Model 186 (this laptop CPU).  
**Measured:** `scripts/eval_gguf.py` on 2026-09-04. Live-component re-run is `scripts/eval_components.py` (same fixtures, live `generate_node` + MCQ task).  
**`.env` / `selectable_default`:** not changed.

| Metric | Value |
|--------|-------|
| Grounded hits | {g} |
| JSON validity | {j} |
| Mean ms | {ms} |
| Skipped | {row.get("skipped")} |

**Verdict:** {verdict}

{sentence}

Raw: `thevindu-models/results/gguf.json` id `{mid}`.
""")
    write(HUB / folder / "version_registry.csv",
          f"candidate_id,role,passed,grounded,json,mean_ms,verdict\n"
          f"{mid},generator,{verdict},{g},{j},{ms},{verdict}\n")


def fill_judge(folder: str, mid: str, name: str, verdict: str, sentence: str) -> None:
    row = judge_row(mid)
    acc = f"{row['accuracy']:.2f}"
    ms = int(round(row["mean_ms"]))
    sys_ok = row.get("system_role_supported")
    write(HUB / folder / "RESULTS.md", f"""# RESULTS — {name}

**Machine:** Windows AMD64 Intel Family 6 Model 186 (this laptop CPU).  
**Measured:** `scripts/eval_gguf.py` on 2026-09-04. Live-component re-run is `scripts/eval_components.py` (live `evaluator.Judge` + SystemMessage).  
**`.env` / `selectable_default`:** not changed.

| Metric | Value |
|--------|-------|
| Gold-label agreement | {acc} |
| Mean ms | {ms} |
| System role supported | {sys_ok} |
| Skipped | {row.get("skipped")} |

**Verdict:** {verdict}

{sentence}

Raw: `thevindu-models/results/gguf.json` id `{mid}`.
""")
    write(HUB / folder / "version_registry.csv",
          f"candidate_id,role,passed,agreement,mean_ms,system_role,verdict\n"
          f"{mid},judge,{verdict},{acc},{ms},{sys_ok},{verdict}\n")


def main() -> None:
    fill_generator(
        "01_generators/qwen25-3b", "qwen25-3b", "Qwen 2.5 3B Instruct",
        "baseline — keep live",
        "Qwen stayed in the passage (1.00) and produced grammar-valid MCQ JSON (1.00) on this laptop. It remains the live generator.",
    )
    fill_generator(
        "01_generators/gemma2-2b", "gemma2-2b", "Gemma 2 2B Instruct",
        "reject",
        "Gemma did not beat Qwen on both metrics: grounded hits 0.67 vs 1.00 and JSON validity 0.00 vs 1.00 — rejected per the stated rule requiring both.",
    )
    fill_generator(
        "01_generators/phi35-mini", "phi35-mini", "Phi-3.5 Mini Instruct",
        "reject",
        "Phi-3.5 did not beat Qwen on grounded hits (0.00 vs 1.00) and JSON validity was lower (0.00 vs 1.00) — rejected per the stated rule requiring both. The run completed; decoded text was garbage bytes under the live empty chat_format contract.",
    )
    fill_judge(
        "02_judges/llama32-3b", "llama32-3b", "Llama 3.2 3B Instruct",
        "baseline — keep live",
        "Llama agreed with all five gold labels (1.00) at 32967 ms. It remains the live judge until four-eyes review of a candidate.",
    )
    fill_judge(
        "02_judges/granite-2b", "granite-2b", "Granite 3.2 2B Instruct",
        "promotable candidate — not flipped",
        "Granite matched Llama on gold-label agreement (1.00 vs 1.00). Mean latency was 36879 ms vs 32967 ms (~12% slower) — not a large regression, so it is a promotable candidate. It is not the live default.",
    )
    fill_judge(
        "02_judges/gemma2-2b", "gemma2-2b-judge", "Gemma 2 2B Instruct (judge)",
        "reject — not a drop-in",
        "Gemma-as-judge agreed 5/5 only after folding the system turn into the user message (`system_role_supported: false`). The live evaluate_node always sends SystemMessage. Rejected as a drop-in.",
    )

    emb = {m["id"]: m for m in REAL["embeddings"]["models"]}
    def emb_line(mid):
        m = emb[mid]
        return m["ndcg@5"], m["gold_in_top3"], m["encode_query_ms_mean"]

    n, g, q = emb_line("minilm-l6")
    write(HUB / "03_embeddings" / "minilm-l6" / "RESULTS.md", f"""# RESULTS — all-MiniLM-L6-v2

**Machine:** this Windows laptop CPU. **Primary fixture:** real company-law PDF.

| NDCG@5 | Gold in top-3 | Query ms |
|--------|---------------|----------|
| {n:.4f} | {g:.2f} | {q:.1f} |

**Verdict:** keep live. Beat E5 and BGE on the real PDF. Do not re-ingest.

Raw: `results/real_pdf.json`.
""")
    n, g, q = emb_line("e5-small")
    write(HUB / "03_embeddings" / "e5-small" / "RESULTS.md", f"""# RESULTS — E5-small-v2

**Machine:** this Windows laptop CPU. **Primary fixture:** real company-law PDF (toy fixture win is not the verdict).

| NDCG@5 | Gold in top-3 | Query ms |
|--------|---------------|----------|
| {n:.4f} | {g:.2f} | {q:.1f} |

**Verdict:** reject. Toy-fixture win reversed on the real PDF. Do not re-ingest onto E5.

Raw: `results/real_pdf.json`.
""")
    n, g, q = emb_line("bge-small")
    write(HUB / "03_embeddings" / "bge-small" / "RESULTS.md", f"""# RESULTS — BGE-small-en-v1.5

**Machine:** this Windows laptop CPU. **Primary fixture:** real company-law PDF.

| NDCG@5 | Gold in top-3 | Query ms |
|--------|---------------|----------|
| {n:.4f} | {g:.2f} | {q:.1f} |

**Verdict:** reject. Lost MiniLM on both the toy fixture and the real PDF.

Raw: `results/real_pdf.json`.
""")
    print("filled per-model RESULTS")


if __name__ == "__main__":
    main()
