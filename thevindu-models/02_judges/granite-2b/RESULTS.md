# RESULTS — Granite 3.2 2B Instruct

**Machine:** Windows AMD64 Intel Family 6 Model 186 (this laptop CPU).  
**Measured:** `scripts/eval_gguf.py` on 2026-09-04. Live-component re-run is `scripts/eval_components.py` (live `evaluator.Judge` + SystemMessage).  
**`.env` / `selectable_default`:** not changed.

| Metric | Value |
|--------|-------|
| Gold-label agreement | 1.00 |
| Mean ms | 36879 |
| System role supported | None |
| Skipped | False |

**Verdict:** promotable candidate — not flipped

Granite matched Llama on gold-label agreement (1.00 vs 1.00). Mean latency was 36879 ms vs 32967 ms (~12% slower) — not a large regression, so it is a promotable candidate. It is not the live default.

Raw: `thevindu-models/results/gguf.json` id `granite-2b`.
