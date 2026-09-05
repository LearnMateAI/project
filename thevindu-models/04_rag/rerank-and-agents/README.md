# RAG comparison — `04_rag/rerank-and-agents`

Two extra **rerankers** and two retrieve **agents**. The live stack is MiniLM-L6 bi-encoder + `cross-encoder/ms-marco-MiniLM-L-6-v2` + (on this branch) hybrid BM25 in front of that reranker.

Weights stay out of git. Agents are recipes, not extra neural nets.

## Reranker A — ms-marco MiniLM-L-12-v2

| | |
|--|--|
| HF | `cross-encoder/ms-marco-MiniLM-L-12-v2` |
| Why | Same MS MARCO recipe as L-6, twice the depth. Tests whether L-6 is the bottleneck without changing the training data. Still CPU-cheap on ~20 pairs. |

## Reranker B — BGE reranker-base

| | |
|--|--|
| HF | `BAAI/bge-reranker-base` |
| Size | ~278 MB |
| Why | Different objective (pair classification vs MS MARCO ranking). Often stronger out-of-domain (legal study questions) than MiniLM-L-6. Logits still go through the sigmoid in `learnmate/llm/rerank.py`. |

Rejected: `bge-reranker-v2-m3` (heavier than this laptop path needs).

## Agent A — `ann-rerank`

Dense top-N (`LEARNMATE_RERANK_CANDIDATES`, default 20) → current cross-encoder → `TOP_K`. This is retrieve when `LEARNMATE_HYBRID_BM25=0`.

## Agent B — `hybrid-rerank`

ANN top 15 ∪ BM25 top 10, deduped, then the **same** reranker. This is retrieve when `LEARNMATE_HYBRID_BM25=1` (current engine default on the feature branch). Eval isolates whether BM25 actually lifts legal keyword queries (`Prescription Ordinance section 10`, `audi alteram partem`) that dense MiniLM can bury.

## 1. Warm reranker caches

```powershell
cd integrated-backend
.\venv\Scripts\python.exe ..\thevindu-models\scripts\fetch_comparison_models.py --rerankers
```

## 2. Score rerankers and agents together

```powershell
.\venv\Scripts\python.exe ..\thevindu-models\scripts\eval_retrieval.py
```

Reranker ablation uses a **fixed MiniLM top-20 pool** so the cross-encoder is the only variable. Agent ablation uses MiniLM + L-6 so the retrieve policy is the only variable.

Metrics: NDCG@5, gold in top-3, Recall@5, predict ms / ~20 pairs.

## 3. Wire a reranker into the live app (only after RESULTS.md)

```
LEARNMATE_RERANK_MODEL=cross-encoder/ms-marco-MiniLM-L-12-v2
```

or

```
LEARNMATE_RERANK_MODEL=BAAI/bge-reranker-base
```

No re-ingest. Restart the backend. First request downloads the new cross-encoder into `data/hf_cache/`.

## 4. Wire an agent

```
LEARNMATE_HYBRID_BM25=0    # ann-rerank
LEARNMATE_HYBRID_BM25=1    # hybrid-rerank (current default)
```

Hybrid needs BM25 sidecars from ingest. Documents ingested before that feature exist can be rebuilt from the vector store on first retrieve; a full re-ingest is cleaner.

## 5. What “better” means

Reranker: gold chunk in top-3 / NDCG@5 on the fixture, without a large ms regression.  
Agent: same metrics plus whether keyword queries (`want: keyword` in the fixture) improve. Do not claim hybrid won if BM25-only chunks are never kept on real chat logs (`retrieval_mix`).
