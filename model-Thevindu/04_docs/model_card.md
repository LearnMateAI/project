# Model Card — LearnMateAI Domain Adapter (Qwen 2.5 + LoRA)

> Filled from `qwen25-lora-20260815-090709` (training run 3). Metrics below are copied
> verbatim from `03_testing_and_versioning/version_registry.csv` — do not invent metrics.

| Field | Value |
|-------|-------|
| Model name | LearnMateAI-Qwen2.5-LoRA (candidate id = training `run_id`) |
| Base model | `Qwen/Qwen2.5-1.5B-Instruct` (default; may be 3B/7B if budget allows) |
| Adaptation | LoRA / PEFT (QLoRA 4-bit training supported) — **not** full fine-tuning |
| Owner track | `model-Thevindu` |
| App integration | Offline artifact; live app reads only a **version pointer** + always keeps API fallback |
| Card status | **EVALUATED — NOT PROMOTED.** Candidate `qwen25-lora-20260815-090709` failed the acceptance gate (§3). |

## 1. Intended use

**In scope:** study support for Sri Lankan legal education (grounded Q&A, summaries, MCQs when a source excerpt is provided).

**Out of scope:** binding legal advice; answering without retrieval as if authoritative.

## 2. Training data

Pipeline: `01_dataset_pipeline` Stages 1–3. Split by whole document. Every pair retains `chunk_id` → `doc_id`.

| Version | Nature | Status |
|---------|--------|--------|
| `lm-legal-smoke-v1` | Synthetic PDFs + mock pairs | Smoke only |
| `lm-legal-smoke-v2` | Synthetic PDFs + first live `gpt-4o-mini` pairs | Smoke only |
| `lm-legal-v0.1` | Real corpus: 21 docs → 19 parsed → 1,280 chunks → 2,534 pairs | **Used for training run 3** (1,590 train / 339 val / 325 test + 280 strict) |

Splits live in `01_dataset_pipeline/processed_v01/` and are gitignored. See `dataset_lineage.md`
for the parse/reject accounting and the known 38% citation-hallucination rate in `summary` pairs.

## 3. Evaluation results

Candidate `qwen25-lora-20260815-090709`, evaluated 2026-08-15 against a `gpt-4o-mini` fallback.
Accuracy row below is the LLM-judge rescoring (the strictest of the three passes recorded).

| Metric | `test` (chapter-held-out) | `test_strict` (document-held-out) | Gate | Verdict |
|--------|---------------------------|-----------------------------------|------|---------|
| Accuracy (LLM-judge) | 0.5569 | 0.6214 | ≥ 0.70 | **FAIL** |
| Groundedness | 0.8769 | 0.9214 | ≥ 0.85 | pass |
| Hallucination rate | 0.1231 | 0.0786 | ≤ 0.15 | pass |
| Latency p95 | 16,368 ms | 14,879 ms | ≤ 8,000 ms | **FAIL** \* |
| Fallback accuracy (`gpt-4o-mini`) | 0.8708 | 0.9179 | must beat | **FAIL** |

\* Latency was measured on Colab T4 with 4-bit QLoRA and sequential `generate`
(`max_new_tokens=256`) — **not** production hardware. It is not a property of the adapter and
should be re-measured before being treated as a real failure.

**Result: `passed=False` on every registry row. Not promoted.** Promotion additionally requires a
signed `promotion_checklist.md` from someone who did not train the run; that has not happened.

Training: 3 epochs, 597 optimizer steps, 93.7 min on a Colab T4, final train/eval loss
1.0377 / 1.2467. Eval loss rose from run 2 (1.1592) while train loss fell — mild overfit.

## 4. Limitations

Bounded by corpus and retrieved excerpts; small LoRA models miss nuance on multi-issue judgments; heuristic groundedness is incomplete.

## 5. Ethical considerations

Not legal advice. Prefer grounded answers. Do not scrape paid databases. Do not mix chat logs into fine-tuning without consent.

## 6. Graceful degradation

If the fine-tuned adapter is unavailable → Gemini (or configured) general API fallback. Never hard-fail solely because the LoRA endpoint is down.

See also `dataset_lineage.md` and `training_run_log.md`.
