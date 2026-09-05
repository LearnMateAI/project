# RESULTS — Gemma 2 2B Instruct

**Machine:** Windows AMD64 Intel Family 6 Model 186 (this laptop CPU).  
**Measured:** `scripts/eval_gguf.py` on 2026-09-04. Live-component re-run is `scripts/eval_components.py` (same fixtures, live `generate_node` + MCQ task).  
**`.env` / `selectable_default`:** not changed.

| Metric | Value |
|--------|-------|
| Grounded hits | 0.67 |
| JSON validity | 0.00 |
| Mean ms | 14856 |
| Skipped | False |

**Verdict:** reject

Gemma did not beat Qwen on both metrics: grounded hits 0.67 vs 1.00 and JSON validity 0.00 vs 1.00 — rejected per the stated rule requiring both.

Raw: `thevindu-models/results/gguf.json` id `gemma2-2b`.
