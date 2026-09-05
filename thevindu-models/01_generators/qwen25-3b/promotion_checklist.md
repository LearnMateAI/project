# Promotion checklist — Qwen 2.5 3B Instruct

See `thevindu-models/testing/promotion_checklist.md`. Candidate `qwen25-3b` (baseline generator).

- [ ] GGUF `qwen2.5-3b-instruct-q4_k_m.gguf` on disk, magic `GGUF`
- [ ] `eval_components.py --generators qwen25-3b` completed, not skipped
- [ ] Beats Qwen on **both** grounded hits and JSON validity (or is the Qwen baseline)
- [ ] `.env` / `selectable_default` unchanged
- [ ] Four-eyes review
