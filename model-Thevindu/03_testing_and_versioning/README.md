# 03 — Testing & versioning

Gate between a trained LoRA adapter and anything the LearnMateAI app might load.

## Contents

| File | Purpose |
|------|---------|
| `acceptance_thresholds.yaml` | Pass/fail contract. Two accuracy names: `in_corpus_accuracy (chapter-held-out)` vs `accuracy (document-held-out)` |
| `evaluate_candidate.ipynb` | Colab T4 eval: both splits, `validate_pairs` groundedness, optional LLM-as-judge, fallback comparison |
| `rescore_eval.py` | Re-score saved `eval_predictions/` without a GPU. `--llm-judge` needs a rotated key in `.env` |
| `version_registry.csv` | One row per evaluated candidate (`passed` true/false). Keep every outcome, including FAIL |
| `eval_predictions/` | Per-item candidate + fallback text and latency for `qwen25-lora-20260815-090709` |
| `promotion_checklist.md` | Literal step-by-step promotion / rollback checklist |

## How to evaluate

1. Train an adapter with Part 2 (must produce `run_record.json`).
2. Set `EVAL_CONFIG["adapter_dir"]` and `dry_run: false` in the notebook. Keys go in Colab Secrets or a gitignored `.env` — never pasted into a cell.
3. Fallback comparison is **mandatory** (`GEMINI_API_KEY` or `OPENAI_API_KEY`).
4. Run all cells. Inspect `PASSED` / `fail_reasons` **per metric** — do not treat a FAIL as “train more”.
5. Only if `passed=True` on **document-held-out** and the checklist is signed by someone else: staging.

## Dry-run mode

`dry_run: true` skips GPU/API loads and writes an intentionally **failing** registry row so the CSV / checklist workflow can be exercised without claiming a real eval.

## Status (`qwen25-lora-20260815-090709` on `lm-legal-v0.1`)

| Item | State |
|------|-------|
| Thresholds + dual metric names | **v2** |
| Live Colab eval on chapter `test` + `test_strict` | **Done — both FAIL** (do not promote) |
| Groundedness re-score with `validate_pairs` | **Done** — 0.877 / 0.921 (clears 0.85); original 0.50 / 0.59 was a regex bug |
| Fallback comparison | **Done** against gpt-4o-mini (not Gemini); candidate loses on token-F1 |
| LLM-as-judge accuracy | **Wired, not run** — rotate the leaked API key first |
| Promotion | **Blocked** |
