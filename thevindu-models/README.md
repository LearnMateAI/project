# thevindu-models

Laptop-sized **drop-in comparisons** for the four live roles in `README-TECHNOLOGIES.md`.
Same idea as `model-Thevindu/`: evidence in git, weights gitignored, numbered folders.

**Branch:** `thevindu-models` only. Do not merge a new silent default to `main`.
Qwen 2.5 3B stays the generator until [RESULTS.md](RESULTS.md) names a winner. The failed
1.5B LoRA stays `experimental: true`.

## Layout

```
thevindu-models/
├── README.md                 ← you are here
├── RESEARCH.md               ← why these families, not another Qwen
├── RESULTS.md                ← bake-off numbers and keep/switch calls
├── comparison_registry.yaml  ← fetch/eval catalog (not the live UI list)
├── 01_generators/            ← Gemma 2 2B, Phi-3.5 Mini
├── 02_judges/                ← Granite 3.2 2B; Gemma-as-judge pointer
├── 03_embeddings/            ← BGE-small, E5-small
├── 04_rag/                   ← L-12 + BGE reranker; ANN vs hybrid agents
├── components/               ← live chat_agent + evaluator re-exports (Dinura contract)
├── testing/                  ← acceptance thresholds, checklist, version registry
├── fixtures/                 ← legal retrieval / generator / judge gold
├── scripts/                  ← fetch + eval (run from integrated-backend)
└── results/                  ← retrieval.json, gguf.json, components.json, real_pdf.json
```

This track is **separate from** `model-Thevindu/` (dataset → LoRA → gate). That work stays
where it is. These folders only compare **live laptop drop-ins**.

## Who to open

| Live role | Baseline | Alt A | Alt B | Runbook |
|-----------|----------|-------|-------|---------|
| Generator | Qwen2.5-3B Q4 | Gemma 2 2B IT | Phi-3.5 Mini | [01_generators/gemma2-2b](01_generators/gemma2-2b/), [01_generators/phi35-mini](01_generators/phi35-mini/) |
| Judge | Llama-3.2-3B Q4 | Gemma 2 2B (judge only) | Granite 3.2 2B | [02_judges/gemma2-2b](02_judges/gemma2-2b/), [02_judges/granite-2b](02_judges/granite-2b/) |
| Embeddings | all-MiniLM-L6-v2 | BGE-small-en-v1.5 | E5-small-v2 | [03_embeddings/bge-small](03_embeddings/bge-small/), [03_embeddings/e5-small](03_embeddings/e5-small/) |
| Reranker + agents | MiniLM-L-6 + hybrid | MiniLM-L-12 / BGE-base; ANN vs hybrid | | [04_rag/rerank-and-agents](04_rag/rerank-and-agents/) |

## Order of work

1. Read [RESEARCH.md](RESEARCH.md).
2. Follow the runbook in the numbered folder.
3. Run `scripts/` from `integrated-backend` (embedders are constructed without the process singleton).
4. Record numbers in [RESULTS.md](RESULTS.md). Promotion is a RESULTS decision, not a registry default.

**This run (2026-09-04 / 2026-09-05):** Qwen generator 1.00/1.00 JSON; Gemma and Phi rejected. Llama and Granite judges 5/5; Granite is a candidate only. Real company-law PDF reversed the toy-fixture E5 and L-12 wins. Each candidate now has Dinura-style `chat_agent/` + `evaluator/` files and Thevindu-style test docs. Live defaults were **not** changed.

## One-shot retrieval eval (no GGUF)

```powershell
cd "integrated-backend"
.\venv\Scripts\python.exe ..\thevindu-models\scripts\eval_retrieval.py
.\venv\Scripts\python.exe ..\thevindu-models\scripts\eval_real_pdf.py
.\venv\Scripts\python.exe ..\thevindu-models\scripts\eval_gguf.py --generators gemma2-2b
```

GGUF generate/judge eval (skips any file that is not on disk):

```powershell
.\venv\Scripts\python.exe ..\thevindu-models\scripts\eval_gguf.py
```

Fetch a comparison GGUF **only when you mean to** (~1.5–2.4 GB each):

```powershell
.\venv\Scripts\python.exe ..\thevindu-models\scripts\fetch_comparison_models.py --gguf gemma2-2b
```
