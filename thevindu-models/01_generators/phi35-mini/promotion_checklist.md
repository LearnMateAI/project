# Promotion checklist — Phi-3.5 Mini Instruct

See `thevindu-models/testing/promotion_checklist.md`. Candidate `phi35-mini` (generator candidate).

- [ ] GGUF `Phi-3.5-mini-instruct-Q4_K_M.gguf` on disk, magic `GGUF`
- [ ] `eval_components.py --generators phi35-mini` completed, not skipped
- [ ] Beats Qwen on **both** grounded hits and JSON validity (or is the Qwen baseline)
- [ ] `.env` / `selectable_default` unchanged
- [ ] Four-eyes review
