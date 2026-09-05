# RESULTS — Qwen 2.5 3B Instruct

**Machine:** Windows AMD64 Intel Family 6 Model 186 (this laptop CPU).  
**Measured:** `scripts/eval_gguf.py` on 2026-09-04. Live-component re-run is `scripts/eval_components.py` (same fixtures, live `generate_node` + MCQ task).  
**`.env` / `selectable_default`:** not changed.

| Metric | Value |
|--------|-------|
| Grounded hits | 1.00 |
| JSON validity | 1.00 |
| Mean ms | 15082 |
| Skipped | False |

**Verdict:** baseline — keep live

Qwen stayed in the passage (1.00) and produced grammar-valid MCQ JSON (1.00) on this laptop. It remains the live generator.

Raw: `thevindu-models/results/gguf.json` id `qwen25-3b`.
