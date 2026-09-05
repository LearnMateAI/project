# Promotion checklist — Gemma 2 2B Instruct (judge role)

Candidate `gemma2-2b-judge` (judge candidate). Pair only with `qwen25-3b`.

- [ ] GGUF `gemma-2-2b-it-Q4_K_M.gguf` magic `GGUF`
- [ ] `eval_components.py --judges gemma2-2b-judge` completed
- [ ] Matches/beats Llama on gold agreement, no large latency regression
- [ ] Accepts `SystemMessage` (live evaluate_node always sends one)
- [ ] `.env` unchanged
- [ ] Four-eyes
