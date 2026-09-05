# RESULTS — Gemma 2 2B Instruct (judge)

**Machine:** Windows AMD64 Intel Family 6 Model 186 (this laptop CPU).  
**Measured:** `scripts/eval_gguf.py` on 2026-09-04. Live-component re-run is `scripts/eval_components.py` (live `evaluator.Judge` + SystemMessage).  
**`.env` / `selectable_default`:** not changed.

| Metric | Value |
|--------|-------|
| Gold-label agreement | 1.00 |
| Mean ms | 38323 |
| System role supported | False |
| Skipped | False |

**Verdict:** reject — not a drop-in

Gemma-as-judge agreed 5/5 only after folding the system turn into the user message (`system_role_supported: false`). The live evaluate_node always sends SystemMessage. Rejected as a drop-in.

Raw: `thevindu-models/results/gguf.json` id `gemma2-2b-judge`.
