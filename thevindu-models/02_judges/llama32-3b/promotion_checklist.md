# Promotion checklist — Llama 3.2 3B Instruct

Candidate `llama32-3b` (baseline judge). Pair only with `qwen25-3b`.

- [ ] GGUF `Llama-3.2-3B-Instruct-Q4_K_M.gguf` magic `GGUF`
- [ ] `eval_components.py --judges llama32-3b` completed
- [ ] Matches/beats Llama on gold agreement, no large latency regression
- [ ] Accepts `SystemMessage` (live evaluate_node always sends one)
- [ ] `.env` unchanged
- [ ] Four-eyes
