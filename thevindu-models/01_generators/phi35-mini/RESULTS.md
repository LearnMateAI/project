# RESULTS — Phi-3.5 Mini Instruct

**Machine:** Windows AMD64 Intel Family 6 Model 186 (this laptop CPU).  
**Measured:** `scripts/eval_gguf.py` on 2026-09-04. Live-component re-run is `scripts/eval_components.py` (same fixtures, live `generate_node` + MCQ task).  
**`.env` / `selectable_default`:** not changed.

| Metric | Value |
|--------|-------|
| Grounded hits | 0.00 |
| JSON validity | 0.00 |
| Mean ms | 17822 |
| Skipped | False |

**Verdict:** reject

Phi-3.5 did not beat Qwen on grounded hits (0.00 vs 1.00) and JSON validity was lower (0.00 vs 1.00) — rejected per the stated rule requiring both. The run completed; decoded text was garbage bytes under the live empty chat_format contract.

Raw: `thevindu-models/results/gguf.json` id `phi35-mini`.
