# RESULTS — laptop model comparison (`thevindu-models`)

**Dates:** 2026-09-03 (36-chunk fixture) and 2026-09-04 (GGUF fetch + real PDF)  
**Branch:** `thevindu-models` (not `main` — nothing here is a live default change)  
**Machine:** Windows CPU laptop (`AMD64`, Intel Family 6 Model 186). Backend venv Python 3.13.7.  
These numbers are **not** Colab T4 numbers and **not** uvicorn chat p95.

**Commands:**

```powershell
cd integrated-backend
.\venv\Scripts\python.exe -u ..\thevindu-models\scripts\eval_retrieval.py
.\venv\Scripts\python.exe -u ..\thevindu-models\scripts\eval_real_pdf.py
.\venv\Scripts\python.exe -u ..\thevindu-models\scripts\eval_gguf.py --generators gemma2-2b
.\venv\Scripts\python.exe -u ..\thevindu-models\scripts\eval_gguf.py --judges granite-2b --generator-under-test qwen25-3b
.\venv\Scripts\python.exe -u ..\thevindu-models\scripts\eval_gguf.py --judges gemma2-2b-judge --generator-under-test qwen25-3b
.\venv\Scripts\python.exe -u ..\thevindu-models\scripts\eval_gguf.py --generators qwen25-3b phi35-mini
.\venv\Scripts\python.exe -u ..\thevindu-models\scripts\eval_gguf.py --judges llama32-3b --generator-under-test qwen25-3b
```

Raw numbers: `results/retrieval.json`, `results/real_pdf.json`, `results/gguf.json`.  
Toy fixture: `fixtures/legal_retrieval.jsonl` (36 chunks, 14 queries).  
Real PDF: `integrated-backend/data/Company-law-part1-notes.pdf` (7 pages → 34 live-ingest chunks, 10 questions).  
GGUF fixtures: `fixtures/generator_prompts.jsonl`, `fixtures/judge_gold.jsonl`.

**Live defaults are unchanged.** Qwen 2.5 3B remains the generator. Llama 3.2 remains the judge. MiniLM-L6 + L-6 reranker remain the retrieve stack. The failed 1.5B LoRA stays `experimental: true`. Nothing in `comparison_registry.yaml` or `models_registry.yaml` was given `selectable_default: true`. `.env` was not edited.

`eval_gguf.py` now hard-blocks same-family generator/judge pairing. Confirmed: `--judges gemma2-2b-judge --generator-under-test gemma2-2b` exits before load.

---

## Decision (read this first)

| Role | Keep live | Named winner on this run | Promote now? | Why |
|------|-----------|--------------------------|--------------|-----|
| Generator | Qwen2.5-3B Q4 | Qwen **1.00 / 1.00** JSON; Gemma 0.67 / 0.00; Phi 0.00 / 0.00 | **No** | Phi does not beat Qwen on both metrics. Gemma already failed JSON. Keep Qwen. |
| Judge | Llama-3.2-3B Q4 | Llama **1.00** @ 33.0 s; Granite **1.00** @ 36.9 s; Gemma-judge 1.00 only after dropping the system turn | **No** | Granite matches agreement with a ~12% latency cost — a promotable *candidate*, not a flipped default. Four-eyes still open. |
| Embeddings | all-MiniLM-L6-v2 | Toy fixture: E5. **Real PDF: MiniLM** (NDCG 0.950 vs E5 0.913) | **No** | The 36-chunk win did not hold on the company-law notes. Query encode on this laptop was ~34 ms MiniLM vs ~61 ms E5 (~1.8×, not the toy ~5×). Quality does not justify a re-ingest. |
| Reranker | MiniLM-L-6 | Toy fixture: L-12. **Real PDF: tie** on NDCG 0.992 / gold-in-top-3 1.0; L-12 ~2× slower (2128 vs 1069 ms) | **No** | Product trial on a real PDF did not show a ranking lift. Do not flip `LEARNMATE_RERANK_MODEL`. |
| RAG agent | hybrid-rerank (already on) | Toy: tie. Real PDF: BM25-only chunks **do** appear in `rerank_kept` (1 of 30 top-3 slots) | **Keep hybrid** | Not a no-op. Most kept chunks are `both`. One BM25-only keep in ten questions is enough to leave the flag on. |

BGE-small lost MiniLM on both the toy fixture and the real PDF. BGE reranker-base remains rejected on toy-fixture latency (~7 s); it was not re-run on the real PDF.

---

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

**How to trial E5** (after a planned re-ingest): see `03_embeddings/e5-small/README.md`. Prefixes must be set or the win disappears.

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

Quality tied the live L-6 model and cost ~11× the time. Out-of-domain hope did not show up on this fixture. Keep it in `04_rag/rerank-and-agents/` as a rerun recipe, not as the next default.

**How to trial L-12:** `LEARNMATE_RERANK_MODEL=cross-encoder/ms-marco-MiniLM-L-12-v2` then restart. See `04_rag/rerank-and-agents/README.md`.

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

## 4. Generators (vs Qwen2.5-3B) — scored 2026-09-04, this Windows laptop CPU

Every file below was on disk with GGUF magic `GGUF` before load. The earlier 377 MB Qwen fragment was deleted and re-fetched clean (2,007.4 MB). Llama was **missing**, not partial; it was fetched separately. Phi is 2,282.4 MB.

| Id | Grounded hits | JSON validity | Mean ms | Verdict |
|----|---------------|----------------|---------|---------|
| qwen25-3b (live) | **1.00** | **1.00** | 15082 | baseline |
| gemma2-2b | 0.67 | 0.00 | 14857 | does not beat on JSON validity → reject |
| phi35-mini | 0.00 | 0.00 | 17822 | **does not beat on grounded hits or JSON** → reject |

Phi-3.5 Mini did not beat Qwen on grounded hits (0.00 vs 1.00) and JSON validity was lower (0.00 vs 1.00) — rejected per the stated rule requiring **both**. The Phi run completed (not an OOM skip) but the decoded text was garbage bytes under the live empty `chat_format` contract; that is a failed drop-in, not a missing file.

Gemma 2 2B matched Qwen’s latency band but JSON validity was 0.00 (the MCQ item parsed as JSON-shaped text that failed the live 4-option / `answer`∈`options` check) — rejected for the same rule.

Qwen 2.5 3B remains the live generator: it is the only scored model that both stayed in the passage and produced grammar-valid MCQ JSON on this laptop.

Do not load Gemma as generator and judge in one process. The script refuses that pairing.

---

## 5. Judges (vs Llama-3.2-3B) — scored 2026-09-04, this Windows laptop CPU

Gold labels: `fixtures/judge_gold.jsonl`. Pass = score ≥ 70. Gemma-judge was only run with `--generator-under-test qwen25-3b`.

| Id | Gold-label agreement | Mean ms | Verdict |
|----|----------------------|---------|---------|
| llama32-3b (live) | **1.00** (5/5) | 32967 | baseline |
| granite-2b | **1.00** (5/5) | 36879 | **matches on agreement, no large latency regression** → promotable candidate |
| gemma2-2b-judge | 1.00 (5/5) after folding system→user | 38323 | **not a drop-in** — `system_role_supported: false` |

Granite 3.2 2B matched Llama on gold-label agreement (1.00 vs 1.00). Mean latency was 36879 ms vs 32967 ms (~12% slower) — not a large regression, so it is a **promotable candidate** under the stated rule. It is **not** the live default: four-eyes review has not happened, and a judge swap must stay a reversible pointer. Keep Llama-3.2 until that review.

Gemma-as-judge also agreed 5/5, but only after the system turn was folded into the user message. The live judge node sends `SystemMessage`. That would be a code change, which Part 3 forbids. Rejected as a drop-in.

---

## 6. Real PDF retrieval (not the 36-chunk fixture)

PDF: `integrated-backend/data/Company-law-part1-notes.pdf` — course notes already in the backend data folder (Companies Act No. 7 of 2007: Salomon, Lee v Lee’s Air Farming, listing capital, unlimited companies, Form 1, s.12, s.23). Chunked with the **live** extract → clean → `pages_to_documents` path. 7 pages → **34 chunks**. 10 questions in `fixtures/real_pdf_queries.jsonl`. Vectors stayed **in memory** — Qdrant was not written, `.env` was not changed, mixed MiniLM/E5 collections were not created.

Machine: same Windows laptop CPU. This is retrieve-stack latency, **not** full chat-turn p95.

### Embeddings on the real PDF

| Id | NDCG@5 | MRR | Gold in top-3 | Query ms (mean) |
|----|--------|-----|---------------|-----------------|
| minilm-l6 (baseline) | **0.9500** | 0.9333 | **1.00** | **33.7** |
| bge-small | 0.9377 | 0.9333 | 1.00 | 63.4 |
| e5-small | 0.9133 | 0.9200 | **0.90** | 61.4 |

E5 missed gold-in-top-3 on r07 (incorporation / Form 1; gold rank 4). Prefixes `query:` / `passage:` were applied through `LearnMateEmbeddings`.

The toy-fixture ~5× query gap (197 vs 38 ms) **did not hold** here (~1.8×). Quality went the other way: MiniLM beat E5. **Do not re-ingest onto E5.** A real PDF that contradicts the toy fixture is the finding, not a number to suppress.

### Rerankers on the real PDF (hybrid MiniLM pool + BM25, then L-6 vs L-12)

| Id | NDCG@5 | Gold in top-3 | Predict ms (mean) |
|----|--------|---------------|-------------------|
| minilm-l6 (baseline) | **0.992** | 1.00 | **1069** |
| minilm-l12 | **0.992** | 1.00 | 2128 |

Quality tie, L-12 twice as slow. BGE reranker-base was not repeated (already rejected at ~7 s on the toy fixture).

Live `.env` was **not** set to L-12 and the API was **not** fully restarted. The in-process path uses the same `CrossEncoder` + sigmoid as `learnmate/llm/rerank.py`. That is enough to refuse a default flip; it is not a uvicorn p95.

### `retrieval_mix` on these 10 questions

Pool (mean): ANN-only 8.3, BM25-only 3.3, both 6.7.  
Rerank kept in top-3, summed over 10 questions:

| Reranker | ann | bm25 | both |
|----------|-----|------|------|
| L-6 | 3 | **1** | 26 |
| L-12 | 4 | **1** | 25 |

BM25-only chunks **do** survive the reranker (once in this set). Do not turn hybrid off. Do not claim hybrid “won retrieval” either — `both` dominates.

---

## 7. What we are not claiming

- Colab T4 p95 from the LoRA eval is not this laptop’s GGUF p95, and this laptop’s retrieve ms is not the app’s full chat p95.
- Train loss, MTEB, or IFEval screenshots are not a substitute for the tables above.
- Recall@5 = 1.0 on the toy fixture does not mean retrieval is solved.
- Gemma 5/5 as judge after a prompt-shape workaround is not a live drop-in.
- No new `selectable_default`. Experimental flags stay as they are.

---

## 8. Promotion gate (Part 3) — all still closed

| Check | Status |
|-------|--------|
| Evaluated on real fixture **and** at least one real ingested/chunked document | Retrieval: yes (toy + company-law PDF). Generators/judges: fixture + gold labels on this laptop. No uvicorn pdf-mode chat p95 (stack was down). |
| Latency labeled with this machine | Yes for scored GGUFs and retrieve. Missing: end-to-end chat p95. |
| Generators/judges scored by gold/judge method, not a proxy | Yes. Qwen 1.00/1.00; Phi 0.00/0.00; Llama and Granite 1.00 gold. |
| Second team member independently reviewed this RESULTS.md | **No.** Four-eyes not done. |
| Change is a reversible pointer/env value | N/A — no pointer was changed. |

Until every box is checked, candidates stay `experimental: true` (or absent from the live default). Same bar as the failed 1.5B LoRA.

---

## 9. Eight-candidate roll-call

| Candidate | Measured? | Result in one line |
|-----------|-----------|---------------------|
| Gemma 2 2B generator | Yes | Grounded 0.67, JSON 0.0 — reject. |
| Phi-3.5 Mini generator | Yes | Grounded 0.00, JSON 0.0, garbage tokens — reject. |
| Granite 3.2 2B judge | Yes | 5/5, ~12% slower than Llama — promotable candidate, not flipped. |
| Gemma 2 2B judge | Yes | 5/5 after dropping system role; not a live drop-in. |
| E5-small embedder | Yes (toy + real PDF) | Toy win, **real PDF loss**. No re-ingest. |
| BGE-small embedder | Yes (toy + real PDF) | Lost MiniLM both times. |
| MiniLM-L-12 reranker | Yes (toy + real PDF) | Toy win, **real PDF tie** at 2× latency. No `.env` flip. |
| BGE reranker-base | Yes (toy only) | Tied L-6, ~11× slower. Skipped on real PDF for that reason. |

---

## 10. End-to-end chat p95 — not measured

```json
{
  "end_to_end_chat_p95_ms": null,
  "machine": "Windows AMD64 Intel Family 6 Model 186, this laptop",
  "measured": "not run — uvicorn :8010 and Qdrant :6335 were down; retrieve-only numbers above are not a serving p95"
}
```

Do not treat §6 retrieve milliseconds as chat p95.

---

## 11. Four-eyes review checklist (do not merge)

A second person should confirm, in writing, on the PR or below:

- [ ] Every number states which machine it was measured on (this Windows laptop CPU, not Colab, not uvicorn p95 unless labeled).
- [ ] The real-PDF result in §6 (not the toy fixture in §1–3) is what the retrieve verdict is based on.
- [ ] The stated decision rules were applied: Phi must beat Qwen on **both** grounded hits and JSON; Granite must match/beat Llama on agreement without a large latency regression.
- [ ] No `selectable_default` or `.env` value changed anywhere in the diff.
- [ ] Raw `results/gguf.json` and `results/real_pdf.json` exist and back every table number, not just the summary sentence.

---

## 12. Component packages (Dinura + Thevindu layout)

Each comparison model now has the same **filenames** as `components-Dinura/learnmate` (`chat_agent/generate.py`, `chat_agent/evaluate.py`, `evaluator/judge.py`, …) and the same **testing docs** as `model-Thevindu/03_testing_and_versioning` (thresholds, checklist, model card, version registry).

Those Python files **re-export** `integrated-backend/learnmate` and bind only the candidate id. That is the replacement: swap the previous GGUF in, keep the live component. They do not fork prompts.

Shared contract: `thevindu-models/components/` and `thevindu-models/testing/`.  
Per-model scores: each folder’s `RESULTS.md`.  
Live-component runner: `scripts/eval_components.py` → `results/components.json`.

`.env` and `selectable_default` stay unchanged.

---

## 13. Next actions (in order)

1. Four-eyes review of this file (PR, do not merge) before any registry flag flips.
2. Leave `.env` and `selectable_default` alone. Granite is a candidate only.
3. Leave hybrid BM25 on.
4. Optional later: one pdf-mode chat turn against the company-law PDF once the stack is up, recorded as its own labeled p95 row.
5. Re-run `eval_components.py` (live `generate_node` / `Judge`) if you want numbers through the exact app prompts rather than `eval_gguf.py`.
6. Do not merge this branch to `main` as a silent model change.
