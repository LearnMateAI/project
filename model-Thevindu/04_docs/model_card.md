# Model Card — LearnMateAI Domain Adapter (Qwen 2.5 + LoRA)

> Template. Fill evaluation tables after a real Part 2/3 run. Do not invent metrics.

| Field | Value |
|-------|-------|
| Model name | LearnMateAI-Qwen2.5-LoRA (candidate id = training `run_id`) |
| Base model | `Qwen/Qwen2.5-1.5B-Instruct` (default; may be 3B/7B if budget allows) |
| Adaptation | LoRA / PEFT (QLoRA 4-bit training supported) — **not** full fine-tuning |
| Owner track | `model-Thevindu` |
| App integration | Offline artifact; live app reads only a **version pointer** + always keeps API fallback |
| Card status | **TEMPLATE** — no production adapter promoted yet |

## 1. Intended use

**In scope:** study support for Sri Lankan legal education (grounded Q&A, summaries, MCQs when a source excerpt is provided).

**Out of scope:** binding legal advice; answering without retrieval as if authoritative.

## 2. Training data

Pipeline: `01_dataset_pipeline` Stages 1–3. Split by whole document. Every pair retains `chunk_id` → `doc_id`.

| Version | Nature | Status |
|---------|--------|--------|
| `lm-legal-smoke-v1` | Synthetic PDFs + mock pairs | Smoke only |
| Real corpus run | Local `processed/` (gitignored) | Not committed |

## 3. Evaluation results

Populate from `03_testing_and_versioning/version_registry.csv` after a real eval.

## 4. Limitations

Bounded by corpus and retrieved excerpts; small LoRA models miss nuance on multi-issue judgments; heuristic groundedness is incomplete.

## 5. Ethical considerations

Not legal advice. Prefer grounded answers. Do not scrape paid databases. Do not mix chat logs into fine-tuning without consent.

## 6. Graceful degradation

If the fine-tuned adapter is unavailable → Gemini (or configured) general API fallback. Never hard-fail solely because the LoRA endpoint is down.

See also `dataset_lineage.md` and `training_run_log.md`.
