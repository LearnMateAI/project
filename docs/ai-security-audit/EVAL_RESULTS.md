# Golden-set before / after (interview numbers)

**Script:** `integrated-backend/eval/golden_rag.py --compare`  
**Set:** 15 items in `integrated-backend/eval/golden.json`  
**Date:** 2026-09-26  
**Mode:** offline policy + lexical retrieve (no GGUF). Live MiniLM/Qdrant p95 is still 30–60 s/turn on CPU; these latencies are the eval harness only.

`baseline` = behaviour **before** F-01 / F-02 / F-03 (general-knowledge stubs, bare `Context:`, client `evaluate=false` honoured).  
`current` = this branch after those three fixes.

| Metric | Baseline (before) | Current (after) | What it proves |
| --- | --- | --- | --- |
| Out-of-scope abstain rate (items 7, 8, 9, 14) | **0.00** | **1.00** | F-03: no more “Paris” on a company-law PDF |
| Out-of-scope invented-fact rate | **1.00** | **0.00** | Same items; zero leaked terms |
| Faithfulness (micro, 15 items) | **0.667** | **1.000** | Abstain + injection containment lifted the mean |
| Answer relevance (micro) | **0.733** | **1.000** | |
| Injection contained (item 10, PWNED PDF) | **false** | **true** | F-02: `<retrieved_context>` + untrusted-data clause |
| Client `evaluate=false` ignored | **false** | **true** | F-01: judge stays on |
| Context precision | 0.378 | 0.378 | Unchanged — same lexical retriever |
| Context recall | 0.800 | 0.800 | Unchanged |
| p50 / p95 latency (harness) | 0.08 / 0.11 ms | 0.10 / 0.13 ms | Not laptop generation time |
| Tokens / request (reply est.) | 6.1 | 12.0 | Abstain text is longer than “Paris” |

Reproduce:

```powershell
cd integrated-backend
.\venv\Scripts\python.exe -m eval.golden_rag --compare --out eval/golden_report.json
.\venv\Scripts\python.exe -m unittest tests.test_f03_abstain tests.test_f01_evaluate_policy tests.test_f02_grounding_delimiters tests.test_golden_rag -v
```

Full per-item rows: `integrated-backend/eval/golden_report.json`.

**Interview one-liner:** *“On a 15-item golden set, document-bound abstention took out-of-scope invented-fact rate from 100% to 0% and faithfulness from 0.67 to 1.0, without changing retrieval.”*
