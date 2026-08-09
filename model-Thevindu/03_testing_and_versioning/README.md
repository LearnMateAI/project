# 03 — Testing & versioning

Gate between a trained LoRA adapter and anything the LearnMateAI app might load.

## Contents

| File | Purpose |
|------|---------|
| `acceptance_thresholds.yaml` | Written-down pass/fail contract (accuracy, groundedness, hallucination rate, latency, fallback comparison) |
| `evaluate_candidate.ipynb` | Loads adapter + run-record, scores held-out test set, compares to fallback, appends registry row |
| `version_registry.csv` | One row per evaluated candidate (`passed` true/false) |
| `promotion_checklist.md` | Literal step-by-step promotion / rollback checklist |

## How to evaluate

1. Train an adapter with Part 2 (must produce `run_record.json`).
2. Set `EVAL_CONFIG["adapter_dir"]` and `dry_run: false` in the notebook.
3. Provide `GEMINI_API_KEY` (or `LM_API_KEY` + `LM_API_BASE`) — fallback comparison is **mandatory**.
4. Run all cells. Inspect `PASSED` / `fail_reasons`.
5. Only if passed: complete `promotion_checklist.md`.

## Dry-run mode

`dry_run: true` (default) skips GPU/API loads and writes an intentionally **failing** registry row so the CSV / checklist workflow can be exercised without claiming a real eval.

## Status

| Item | State |
|------|-------|
| Thresholds + checklist + registry schema | **Ready** |
| Notebook scoring + fail-closed gates | **Ready** |
| Real adapter eval + live Gemini comparison | **Not executed** (no trained adapter in-repo yet) |
