# Scripts

Run from `integrated-backend` so `learnmate` imports and `HF_HOME` redirection apply.

| Script | What it does |
|--------|----------------|
| `fetch_comparison_models.py` | Warm embedders/rerankers (default). `--gguf <id>` downloads one GGUF. |
| `eval_retrieval.py` | MiniLM vs BGE vs E5; L-6 vs L-12 vs BGE reranker; ann vs hybrid. Writes `../results/retrieval.json`. |
| `eval_gguf.py` | Generator + judge smoke. Skips missing GGUFs. Hard-blocks same-family generator/judge pairing. Merges `../results/gguf.json` across runs. |
| `eval_real_pdf.py` | MiniLM vs E5 and L-6 vs L-12 on a real legal PDF (live ingest chunker, in-memory vectors). Writes `../results/real_pdf.json`. |
| `common.py` | Registry parser and paths. |

```powershell
.\venv\Scripts\python.exe ..\thevindu-models\scripts\eval_retrieval.py
.\venv\Scripts\python.exe ..\thevindu-models\scripts\eval_real_pdf.py
.\venv\Scripts\python.exe ..\thevindu-models\scripts\eval_gguf.py --generators gemma2-2b
.\venv\Scripts\python.exe ..\thevindu-models\scripts\eval_gguf.py --generators qwen25-3b phi35-mini
.\venv\Scripts\python.exe ..\thevindu-models\scripts\eval_gguf.py --judges llama32-3b --generator-under-test qwen25-3b
```
