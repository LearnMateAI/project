# BGE-small-en-v1.5 — `model-bge-small`

**Role:** embedding candidate A (vs live `all-MiniLM-L6-v2`).

| | |
|--|--|
| HF id | `BAAI/bge-small-en-v1.5` |
| Size | ~33M, **384-d**, ~130 MB |
| Query prefix | `Represent this sentence for searching relevant passages:` |
| Doc prefix | (empty) |
| Live default? | **No.** Changing embedder requires **re-ingest**. Old MiniLM vectors are not comparable. |

## Why this model

Same vector width as MiniLM, so Qdrant collection dim stays 384 after a re-embed. Stronger public BEIR-style retrieval than MiniLM. Already named in `learnmate/config.py`. Instruction prefix on the **query** only — that asymmetry is the point.

Risks: forgetting the query prefix quietly tanks recall. Must re-ingest every PDF. Retune `LEARNMATE_RELEVANCE_THRESHOLD` if you ever turn reranking off; BGE cosine is not MiniLM cosine.

## 1. Fetch / warm cache

```powershell
cd integrated-backend
.\venv\Scripts\python.exe ..\docs\thevindu-models\scripts\fetch_comparison_models.py --embeddings
```

Or just run the retrieval eval; it constructs `LearnMateEmbeddings(model_name=..., query_prefix=...)` and downloads on first encode.

## 2. Score against MiniLM and E5 (in-memory, no Qdrant)

```powershell
.\venv\Scripts\python.exe ..\docs\thevindu-models\scripts\eval_retrieval.py
```

Primary metrics: Recall@5, MRR, NDCG@5 on `docs/thevindu-models/fixtures/legal_retrieval.jsonl`. Secondary: encode ms.

## 3. Wire into the live app (only after RESULTS.md)

```
LEARNMATE_EMBEDDING_MODEL=BAAI/bge-small-en-v1.5
LEARNMATE_EMBEDDING_QUERY_PREFIX=Represent this sentence for searching relevant passages:
LEARNMATE_EMBEDDING_DOC_PREFIX=
```

Then **re-ingest** every document (`force=True`). Start-up already warns if stored `embedding_model` ≠ current config. Do not mix BGE queries against MiniLM chunks.

## 4. What “better” means

Beat MiniLM on NDCG@5 / Recall@5 on the legal fixture without a large encode-time regression. A public MTEB screenshot is not a substitute for this corpus’s questions.
