# Promotion checklist — Granite 3.2 2B Instruct

Candidate `granite-2b` (judge candidate). Pair only with `qwen25-3b`.

- [ ] GGUF `ibm-granite_granite-3.2-2b-instruct-Q4_K_M.gguf` magic `GGUF`
- [ ] `eval_components.py --judges granite-2b` completed
- [ ] Matches/beats Llama on gold agreement, no large latency regression
- [ ] Accepts `SystemMessage` (live evaluate_node always sends one)
- [ ] `.env` unchanged
- [ ] Four-eyes
