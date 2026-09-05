# Promotion checklist — Gemma 2 2B Instruct

See `thevindu-models/testing/promotion_checklist.md`. Candidate `gemma2-2b` (generator candidate).

- [ ] GGUF `gemma-2-2b-it-Q4_K_M.gguf` on disk, magic `GGUF`
- [ ] `eval_components.py --generators gemma2-2b` completed, not skipped
- [ ] Beats Qwen on **both** grounded hits and JSON validity (or is the Qwen baseline)
- [ ] `.env` / `selectable_default` unchanged
- [ ] Four-eyes review
