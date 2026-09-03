# thevindu-models

Laptop-sized **drop-in comparisons** for the four live roles in `README-TECHNOLOGIES.md`.
Qwen 2.5 3B stays the generator until `RESULTS.md` names a winner. The failed 1.5B LoRA
stays `experimental: true`.

**Branch:** `thevindu-models` only. Do not merge a new silent default to `main`.

| Live role | Baseline | Alt A | Alt B | Runbook |
|-----------|----------|-------|-------|---------|
| Generator | Qwen2.5-3B Q4 | Gemma 2 2B IT | Phi-3.5 Mini | `model-gemma2-2b/`, `model-phi35-mini/` |
| Judge | Llama-3.2-3B Q4 | Gemma 2 2B (judge only) | Granite 3.2 2B | `model-gemma2-2b/`, `model-granite-2b/` |
| Embeddings | all-MiniLM-L6-v2 | BGE-small-en-v1.5 | E5-small-v2 | `model-bge-small/`, `model-e5-small/` |
| Reranker | ms-marco MiniLM-L-6 | MiniLM-L-12 | BGE reranker-base | `model-rag/` |
| RAG agent | (recipe, not weights) | `ann-rerank` | `hybrid-rerank` | `model-rag/` |

Weights are **not** in git. Each `model-<name>/` folder is a rerun recipe, same idea as
`model-Thevindu/`.

## Order of work

1. Read [RESEARCH.md](RESEARCH.md) — why these families, not another Qwen.
2. Follow the runbook in the model folder you are testing.
3. Run the shared scripts in `scripts/` (they construct embedders **without** the process
   singleton, so MiniLM and BGE can be scored in one process).
4. Record numbers in [RESULTS.md](RESULTS.md). Promotion is a RESULTS decision, not a
   registry default change.

## One-shot retrieval eval (no GGUF)

From the repo root, using the backend venv:

```powershell
cd "integrated-backend"
.\venv\Scripts\python.exe ..\docs\thevindu-models\scripts\eval_retrieval.py
```

That scores embedders, rerankers, and the two retrieve agents on
`fixtures/legal_retrieval.jsonl`. First run downloads ~700 MB of sentence-transformers
weights into `integrated-backend/data/hf_cache/` (gitignored).

GGUF generate/judge eval (skips any file that is not on disk):

```powershell
.\venv\Scripts\python.exe ..\docs\thevindu-models\scripts\eval_gguf.py
```

Fetch a comparison GGUF **only when you mean to** (~1.5–2.4 GB each):

```powershell
.\venv\Scripts\python.exe ..\docs\thevindu-models\scripts\fetch_comparison_models.py --gguf gemma2-2b
```
