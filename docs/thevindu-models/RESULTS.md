# RESULTS — laptop model comparison (`thevindu-models`)

**Date:** 2026-09-03  
**Branch:** `thevindu-models` (not `main`)  
**Machine:** Windows CPU, backend venv, unauthenticated Hugging Face downloads  
**Command:**

```powershell
cd integrated-backend
.\venv\Scripts\python.exe -u ..\docs\thevindu-models\scripts\eval_retrieval.py
.\venv\Scripts\python.exe -u ..\docs\thevindu-models\scripts\eval_gguf.py
```

Raw numbers: `results/retrieval.json`, `results/gguf.json`.  
Fixture: `fixtures/legal_retrieval.jsonl` (36 chunks, 14 queries after distractors).  
GGUF fixture: `fixtures/generator_prompts.jsonl`, `fixtures/judge_gold.jsonl`.

**Live defaults are unchanged.** Qwen 2.5 3B remains the generator. The failed 1.5B LoRA stays `experimental: true`. Nothing in `models_registry.yaml` was given `selectable_default: true`.

---

## Decision (read this first)

| Role | Keep live | Named winner on this run | Promote now? | Why |
|------|-----------|--------------------------|--------------|-----|
| Generator | Qwen2.5-3B Q4 | *unevaluated* (no GGUF on disk) | **No** | Cannot beat a missing file. Next trial: Gemma 2 2B, then Phi-3.5 Mini (`eval_gguf.py --fetch`). |
| Judge | Llama-3.2-3B Q4 | *unevaluated* | **No** | Same. Next trial: Granite 3.2 2B, then Gemma-as-judge **only** with a Qwen or Phi generator. |
| Embeddings | all-MiniLM-L6-v2 | **E5-small-v2** (NDCG@5 0.938 vs 0.921) | **Not yet** | Quality win is real on this fixture; query encode is ~5× slower and a switch needs a full re-ingest. |
| Reranker | MiniLM-L-6 | **MiniLM-L-12** (NDCG@5 0.974 vs 0.947) | **Next product trial** | Same MS MARCO recipe, better ranking, ~2× time (1.3 s vs 0.6 s per 20 pairs) — still cheap vs a 3B generate. No re-ingest. |
| RAG agent | hybrid-rerank (already on) | **Tie** with ann-rerank | **Keep hybrid** | Identical Recall/MRR/NDCG. The script’s “hybrid win” is a tie-break, not a lift. |

BGE-small **lost** to MiniLM on this legal fixture. BGE reranker-base **tied** L-6 on quality and was ~11× slower. Neither BGE is the next swap.

---

## 1. Embeddings (vs all-MiniLM-L6-v2)

In-memory cosine, 384-d, prefixes applied through `LearnMateEmbeddings` (not the process singleton).

| Id | HF | NDCG@5 | MRR | Recall@5 | Query ms (mean) | Corpus encode ms |
|----|----|--------|-----|----------|-----------------|------------------|
| minilm-l6 (baseline) | `all-MiniLM-L6-v2` | 0.9209 | 0.8929 | 1.00 | 37.7 | 11448 |
| bge-small | `BAAI/bge-small-en-v1.5` | 0.9116 | 0.8810 | 1.00 | 72.9 | 11857 |
| **e5-small** | `intfloat/e5-small-v2` | **0.9379** | **0.9167** | 1.00 | 196.6 | 13887 |

Recall@5 is saturated: every model put the gold chunk in the top five. Ranking quality is what moved.

Where they differed (gold rank):

| Query | MiniLM | BGE | E5 | Note |
|-------|--------|-----|-----|------|
| q02 audi alteram partem | 2 | 2 | 2 | Distractor d09 (“heard” in ordinary English) beats all three to rank 1 |
| q10 four elements of negligence | 2 | 3 | 3 | MiniLM closer; d12 recites the same four elements |
| q14 medical prescription vs Ordinance | 2 | 2 | **1** | E5’s query/passage prefixes help the keyword trap |

### Why E5 was chosen as the embedder winner

1. **Asymmetric training matches the job.** Questions vs statute-like chunks is what `query:` / `passage:` was trained for. MiniLM embeds both sides the same way. That showed up on q14, the planted lexical trap.
2. **Same 384-d width** as live MiniLM, so Qdrant does not need a new vector size — only a re-ingest.
3. **Not BGE.** BGE-small is the usual “upgrade MiniLM” suggestion in our own config comments. On *this* legal-study fixture it was slightly worse than MiniLM (q10 rank 3 vs 2). Promoting BGE because MTEB likes it would have been the wrong call here.

### Why we still do not flip `LEARNMATE_EMBEDDING_MODEL`

- Re-ingest of every PDF is mandatory. Mixed MiniLM/E5 vectors are silent garbage.
- Mean query encode 197 ms vs 38 ms. On a laptop that cost is paid every chat retrieve, not once.
- 14 queries is enough to rank three small models, not enough to declare an IR championship. Re-run on a real ingested PDF before changing `.env`.

**How to trial E5** (after a planned re-ingest): see `model-e5-small/README.md`. Prefixes must be set or the win disappears.

---

## 2. Rerankers (vs ms-marco MiniLM-L-6-v2)

Fixed MiniLM top-20 candidate pool, so the cross-encoder is the only variable. Sigmoid as in `learnmate/llm/rerank.py`.

| Id | HF | NDCG@5 | MRR | Gold in top-3 | ms / ~20 pairs |
|----|----|--------|-----|---------------|----------------|
| minilm-l6 (baseline) | `cross-encoder/ms-marco-MiniLM-L-6-v2` | 0.9473 | 0.9286 | 1.00 | 610 |
| **minilm-l12** | `cross-encoder/ms-marco-MiniLM-L-12-v2` | **0.9736** | **0.9643** | 1.00 | 1302 |
| bge-reranker-base | `BAAI/bge-reranker-base` | 0.9473 | 0.9286 | 1.00 | 7047 |

### Why MiniLM-L-12 was chosen as the reranker winner

1. **Same recipe, extra depth.** It is the ablation RESEARCH asked for: is L-6 the bottleneck? Yes, a little — NDCG +0.026, MRR +0.036 — without changing training data or the rest of the stack.
2. **Latency is still in the noise next to generation.** 1.3 s vs 0.6 s on CPU, against a 3B generate measured in tens of seconds. BGE-base at 7 s is not.
3. **No re-ingest.** One env line.

### Why BGE reranker-base was rejected

Quality tied the live L-6 model and cost ~11× the time. Out-of-domain hope did not show up on this fixture. Keep it in `model-rag/` as a rerun recipe, not as the next default.

**How to trial L-12:** `LEARNMATE_RERANK_MODEL=cross-encoder/ms-marco-MiniLM-L-12-v2` then restart. See `model-rag/README.md`.

---

## 3. Retrieve agents (ann-rerank vs hybrid-rerank)

Same MiniLM + L-6 reranker. Hybrid = ANN top 15 ∪ BM25 top 10, matching `retrieve.py`.

| Id | NDCG@5 | MRR | Recall@5 | Gold in top-3 | Mean pool |
|----|--------|-----|----------|---------------|-----------|
| ann-rerank | 0.9473 | 0.9286 | 1.00 | 1.00 | 20.0 |
| hybrid-rerank | 0.9473 | 0.9286 | 1.00 | 1.00 | 19.07 |

Dense already had every gold in the top 20. BM25 did not add a unique gold that ANN missed, so the reranker saw almost the same shortlist. `eval_retrieval.py`’s `fixture_winners.agents_by_ndcg@5 = hybrid-rerank` is a **tie broken in favour of the non-baseline**, not evidence that hybrid retrieved better.

**Why we still keep hybrid as the live agent:** it is already the engine default on this lineage (`LEARNMATE_HYBRID_BM25=1`), it does not hurt this fixture, and keyword statutes on a *real* PDF are exactly where BM25 is supposed to help. Confirm on live `retrieval_mix` (if `bm25` never appears in `rerank_kept`, say so rather than assuming a win). Do not turn it off because of a 36-chunk toy corpus.

---

## 4. Generators (vs Qwen2.5-3B) — not scored

`eval_gguf.py` skipped every generator: this checkout has **no `integrated-backend/models/*.gguf`**.

| Id | Family | Expected file | Status |
|----|--------|---------------|--------|
| qwen25-3b (live) | Qwen 2.5 | `qwen2.5-3b-instruct-q4_k_m.gguf` | missing here |
| gemma2-2b | Gemma 2 | `gemma-2-2b-it-Q4_K_M.gguf` (~1.71 GB) | missing |
| phi35-mini | Phi-3.5 | `Phi-3.5-mini-instruct-Q4_K_M.gguf` (~2.39 GB) | missing |

**Why Gemma and Phi were shortlisted (not scored):** see `docs/thevindu-models/RESEARCH.md` and the runbooks. Short version:

- **Gemma 2 2B** — different pretrain from the failed Qwen LoRA; IFEval-class instruction following at 2B; smaller prefill than 3B.
- **Phi-3.5 Mini** — ~3.8B dense, MIT, schema-following reputation, still in the Q4 laptop band.

**Why we keep Qwen 3B until those files are fetched and `eval_gguf.py` is re-run:** the live generator already writes grammar-constrained JSON in production. Switching on a blog benchmark after the 1.5B LoRA failed the legal gate would repeat that mistake.

```powershell
.\venv\Scripts\python.exe ..\docs\thevindu-models\scripts\fetch_comparison_models.py --gguf gemma2-2b
.\venv\Scripts\python.exe ..\docs\thevindu-models\scripts\eval_gguf.py --generators qwen25-3b gemma2-2b
```

Repeat for `phi35-mini`. Metrics: grounded substring hits, MCQ JSON validity, mean ms. **Do not load Gemma as generator and judge together.**

---

## 5. Judges (vs Llama-3.2-3B) — not scored

Same skip: no GGUFs.

| Id | Pair only with | Expected file |
|----|----------------|---------------|
| llama32-3b (live) | Qwen / Gemma / Phi / Granite generators | `Llama-3.2-3B-Instruct-Q4_K_M.gguf` |
| gemma2-2b-judge | Qwen or Phi generators **only** | same file as generator Gemma |
| granite-2b | Qwen, Phi, or Gemma generators | `ibm-granite_granite-3.2-2b-instruct-Q4_K_M.gguf` (~1.55 GB) |

**Why Granite was shortlisted:** RAG-style “stick to the documents” training is the judge’s job; Apache-2.0; smallest Q4 of the set.

**Why Gemma-as-judge is allowed only as a second opinion on Qwen/Phi:** same weights grading themselves is the bug Llama exists to prevent.

Keep Llama 3.2 until `judge_gold.jsonl` accuracy is measured on this laptop.

---

## 6. What we are not claiming

- Colab T4 p95 from the LoRA eval is not this laptop’s GGUF p95.
- Train loss, MTEB, or IFEval screenshots are not a substitute for the tables above.
- Recall@5 = 1.0 does not mean retrieval is solved; it means this 36-chunk set is easy at k=5. NDCG/MRR are the discriminative numbers.
- No new `selectable_default`. The UI may list Gemma/Phi as experimental **after** their GGUFs exist; Qwen remains `default_id`.

---

## 7. Next actions (in order)

1. Product trial of **MiniLM-L-12** reranker (one env var, restart, one pdf-mode chat). If NDCG-style feel holds and p95 retrieve stays acceptable, it is the first default worth changing.
2. Fetch Qwen + Gemma GGUFs and run `eval_gguf.py`. Only then argue a generator swap.
3. If a re-ingest window exists, trial **E5-small** with both prefixes, then re-run this script plus one real PDF.
4. Leave hybrid BM25 on; inspect `retrieval_mix` on real chats.
5. Do not merge this branch to `main` as a silent model change.
