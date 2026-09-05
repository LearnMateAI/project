# RESULTS — Llama 3.2 3B Instruct

**Machine:** Windows AMD64 Intel Family 6 Model 186 (this laptop CPU).  
**Measured:** `scripts/eval_gguf.py` on 2026-09-04. Live-component re-run is `scripts/eval_components.py` (live `evaluator.Judge` + SystemMessage).  
**`.env` / `selectable_default`:** not changed.

| Metric | Value |
|--------|-------|
| Gold-label agreement | 1.00 |
| Mean ms | 32967 |
| System role supported | True |
| Skipped | False |

**Verdict:** baseline — keep live

Llama agreed with all five gold labels (1.00) at 32967 ms. It remains the live judge until four-eyes review of a candidate.

Raw: `thevindu-models/results/gguf.json` id `llama32-3b`.
