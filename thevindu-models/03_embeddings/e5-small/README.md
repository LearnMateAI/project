# E5-small-v2 — `03_embeddings/e5-small`

**Role:** embedding candidate B (vs live `all-MiniLM-L6-v2` and vs BGE-small).

| | |
|--|--|
| HF id | `intfloat/e5-small-v2` |
| Size | ~33M, **384-d** |
| Query prefix | `query:` |
| Doc prefix | `passage:` |
| Live default? | **No.** Re-ingest required. |

## Why this model

Asymmetric query/doc training matches “question vs statute chunk”. Same 384-d laptop budget as MiniLM and BGE. Different recipe from BGE (Microsoft E5 vs BAAI), so a win is not “all the same Chinese retrieval models”. Config already documents both prefixes.

Risks: empty prefixes put queries and passages in the wrong space. Re-ingest required. Do not compare E5 vectors to MiniLM or BGE in one Qdrant collection.

## 1. Fetch / warm cache

```powershell
cd integrated-backend
.\venv\Scripts\python.exe ..\thevindu-models\scripts\fetch_comparison_models.py --embeddings
```

## 2. Score

```powershell
.\venv\Scripts\python.exe ..\thevindu-models\scripts\eval_retrieval.py
```

Same fixture and metrics as `03_embeddings/bge-small`. The script scores MiniLM, BGE, and E5 in one run.

## 3. Wire into the live app (only after RESULTS.md)

```
LEARNMATE_EMBEDDING_MODEL=intfloat/e5-small-v2
LEARNMATE_EMBEDDING_QUERY_PREFIX=query:
LEARNMATE_EMBEDDING_DOC_PREFIX=passage:
```

Re-ingest all PDFs. Confirm `/api/health` and a chat retrieve log still return the expected top chunks.

## 4. What “better” means

Same table as BGE: Recall@5, MRR, NDCG@5, encode time. Pick at most **one** embedder to promote; mixing families in Qdrant is undefined.
