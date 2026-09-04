# Scripts

Run from `integrated-backend` so `learnmate` imports and `HF_HOME` redirection apply.

| Script | What it does |
|--------|----------------|
| `fetch_comparison_models.py` | Warm embedders/rerankers (default). `--gguf <id>` downloads one GGUF. |
| `eval_retrieval.py` | MiniLM vs BGE vs E5; L-6 vs L-12 vs BGE reranker; ann vs hybrid. Writes `../results/retrieval.json`. |
| `eval_gguf.py` | Generator + judge smoke. Skips missing GGUFs. Writes `../results/gguf.json`. |
| `common.py` | Registry parser and paths. |

```powershell
.\venv\Scripts\python.exe ..\thevindu-models\scripts\eval_retrieval.py
.\venv\Scripts\python.exe ..\thevindu-models\scripts\eval_gguf.py
```
