# Model comparison research — `thevindu-models`

**Branch:** `thevindu-models` (from `thevindu-feature`). Do not merge a new silent default to `main` until this folder’s `RESULTS.md` names a winner **and** the same gate as `model-Thevindu/03_testing_and_versioning/acceptance_thresholds.yaml` has been considered.

**Why this branch exists.** The live generator is still **Qwen2.5-3B-Instruct Q4**. The domain LoRA `qwen25-lora-20260815-090709` **failed** that gate (LLM-judge accuracy 0.557 / 0.621 vs ≥ 0.70; lost to the API fallback). Production correctly kept the 3B base. This track asks: *are there better laptop-sized drop-ins for each of the four roles in README-TECHNOLOGIES.md?*

The four live roles:

| Role | Current | Size | Constraint |
|------|---------|------|------------|
| Generator | Qwen2.5-3B-Instruct Q4 | ~2 GB GGUF | Writes chat + study JSON; one llama.cpp context |
| Judge | Llama-3.2-3B-Instruct Q4 | ~2 GB GGUF | **Different family** from the generator |
| Embeddings | `all-MiniLM-L6-v2` | ~90 MB | 384-d vectors; CPU ingest |
| Reranker | `ms-marco-MiniLM-L-6-v2` | ~90 MB | Cross-encoder on ~20 pairs |

Each role gets **two alternatives**, not a second copy of the same family. Q4 GGUFs stay in the ~1.5–2.4 GB band so a laptop can still load generator + judge.

Weights are **not** in git. Each `model-<name>/` folder is a runbook + eval recipe, same idea as `model-Thevindu/` (evidence in git, binaries gitignored).

---

## Generator (vs Qwen2.5-3B-Instruct)

Qwen 2.5 3B stays the baseline: ChatML, grammar-constrained JSON, already wired. We do **not** pick another Qwen size as “the other two” — that would not test a different pretrain.

### Candidate A — Gemma 2 2B Instruct (`model-gemma2-2b`)

| | |
|--|--|
| HF (original) | `google/gemma-2-2b-it` |
| GGUF | `bartowski/gemma-2-2b-it-GGUF` / `gemma-2-2b-it-Q4_K_M.gguf` (~1.71 GB) |
| Family | Gemma 2 (Google) — **not** Qwen, **not** Llama |
| Why shortlisted | Same job (instruct, local, Q4). Sliding-window Gemma 2 is strong on IFEval-class instruction following at 2B, which is the skill that makes 3B JSON study-material work. Different tokenizer/template than Qwen so a win is a real architecture win, not a cousin of the failed LoRA. Smaller than 3B → cheaper prefill on CPU. |
| Risks | Gemma licence (gated acknowledge on some HF repos). Chat template forbids a system turn in some converters — our prompts put instructions in the user/task text. 2B may be weaker on long IRAC than 3B. |

### Candidate B — Phi-3.5 Mini Instruct (`model-phi35-mini`)

| | |
|--|--|
| HF (original) | `microsoft/Phi-3.5-mini-instruct` |
| GGUF | `bartowski/Phi-3.5-mini-instruct-GGUF` / `Phi-3.5-mini-instruct-Q4_K_M.gguf` (~2.39 GB) |
| Family | Phi-3 (Microsoft) — **not** Qwen, **not** Llama |
| Why shortlisted | 3.8B dense, same Q4 laptop band. Published numbers put it near GPT-3.5-Turbo on several English benches; strong at following tight schemas (MCQ JSON). MIT licence. Long context in the original card (we still cap `n_ctx` like the rest of the app). |
| Risks | Slightly larger RAM than Qwen 3B Q4. Phi chat tokens (`<\|user\|>`) must come from GGUF metadata — leave `chat_format` empty unless llama.cpp mis-detects. |

**Rejected as generator “alts”:** another Qwen 2.5 (1.5B/7B) — 1.5B already failed the legal gate; 7B Q4 is ~4 GB and breaks the two-GGUF laptop budget. Llama-3.2-3B as generator — that **is** the judge family; pairing them would collapse the second-opinion rule.

---

## Judge (vs Llama-3.2-3B-Instruct)

The judge must stay a **different family from whichever generator is live**. If the generator becomes Gemma, Llama or Granite or Phi can judge. If the generator stays Qwen, Gemma or Granite or Phi can judge. Llama-3.2 remains the baseline.

### Candidate A — Gemma 2 2B Instruct as judge (`model-gemma2-2b`, role=judge)

Same GGUF as generator candidate A. **Never load it as generator and judge at once** (one process, two roles, same weights = the bug the Llama judge exists to prevent). Eval pairs Gemma-judge **only** with Qwen or Phi as generator.

Why: 2B is enough for short JSON verdicts (`score`, `reasoning`). Faster than 3B on CPU. Different family from Qwen.

### Candidate B — Granite 3.2 2B Instruct (`model-granite-2b`)

| | |
|--|--|
| HF (original) | `ibm-granite/granite-3.2-2b-instruct` |
| GGUF | `bartowski/ibm-granite_granite-3.2-2b-instruct-GGUF` / `ibm-granite_granite-3.2-2b-instruct-Q4_K_M.gguf` (~1.55 GB) |
| Family | Granite (IBM), Apache-2.0 |
| Why shortlisted | Instruct model trained to stick to provided documents (RAG-style system text). That is the judge’s job: grade against a passage, not invent law. Smallest of the GGUF candidates. Apache licence is easy for a student project. |
| Risks | Chat template is Granite-specific; leave `chat_format` empty so llama.cpp reads the GGUF. 2B may be softer than Llama 3.2 3B on “unsupported claim = fail”. |

**Rejected:** Phi-3.5 as **both** generator-winner and judge — same-family grading. Use Phi as generator **or** judge in a given pairing, not both.

---

## Embeddings (vs all-MiniLM-L6-v2)

MiniLM-L6 is 22M, 384-d, no instruction prefix, fast ingest. Config already documents BGE/E5 prefixes in `learnmate/config.py`.

### Candidate A — BGE-small-en-v1.5 (`model-bge-small`)

| | |
|--|--|
| HF | `BAAI/bge-small-en-v1.5` |
| Size | ~33M, 384-d, ~130 MB |
| Prefix | Query only: `Represent this sentence for searching relevant passages:` |
| Why | Same width as MiniLM so Qdrant dim stays 384 after a **re-ingest**. Stronger than MiniLM on BEIR-style retrieval in public numbers. Already named in our config comments. |
| Risks | Forgetting the query prefix quietly tanks recall. Old MiniLM vectors are **not** comparable — must re-embed. |

### Candidate B — E5-small-v2 (`model-e5-small`)

| | |
|--|--|
| HF | `intfloat/e5-small-v2` |
| Size | ~33M, 384-d |
| Prefix | Query: `query: ` / Doc: `passage: ` |
| Why | Asymmetric query/doc training matches “question vs statute chunk”. Same 384-d laptop budget. Different recipe from BGE so a win is not “all Chinese labs look the same”. |
| Risks | Empty prefixes = wrong space. Re-ingest required. |

**Rejected:** `bge-large` / `e5-large` (1024-d, slow CPU ingest). `all-mpnet-base-v2` (768-d) — would force a new Qdrant collection width.

---

## Reranker (vs ms-marco-MiniLM-L-6-v2)

The cross-encoder only sees ~20 pairs; size can grow a little.

### Candidate A — ms-marco-MiniLM-L-12-v2 (`model-rag` rerank slot)

| | |
|--|--|
| HF | `cross-encoder/ms-marco-MiniLM-L-12-v2` |
| Why | Same MS MARCO training as L-6, twice the depth. Ablation of “is L-6 the bottleneck?” without changing the data recipe. Still CPU-cheap. |

### Candidate B — BGE reranker base (`model-rag` rerank slot)

| | |
|--|--|
| HF | `BAAI/bge-reranker-base` |
| Size | ~278 MB |
| Why | Different objective (BGE pair classification vs MS MARCO). Often stronger on out-of-domain (legal) than MS MARCO-only MiniLM. Still one forward pass per pair. |
| Risks | Logits may sit on a different scale; we already sigmoid in `rerank.py`. Slightly slower than L-6. |

**Rejected:** `bge-reranker-v2-m3` (multilingual, heavier than this laptop path needs).

---

## Retrieval *agents* (not extra neural nets)

Two agent recipes on top of the embedder+reranker, because “RAG quality” is retrieve policy as much as weights:

| Agent id | Recipe |
|----------|--------|
| `ann-rerank` | Dense top-N → current cross-encoder (today when BM25 is off) |
| `hybrid-rerank` | ANN ∪ BM25 → same reranker (`LEARNMATE_HYBRID_BM25=1`) |

Eval scores **recall@k** and **MRR** on a fixed legal fixture (`fixtures/legal_retrieval.jsonl`). That isolates embedder vs reranker vs agent without a 3B generate.

---

## What “better” means (do not mix these)

| Role | Primary metric | Secondary | Must not |
|------|----------------|-----------|----------|
| Generator | Grounded legal Q&A on a **held-out excerpt** (same spirit as Gate 2) | JSON validity rate, tokens/s | Promote because loss was lower |
| Judge | Agreement with a gold pass/fail on planted unsupported citations | Latency | Same family as the generator under test |
| Embeddings | Recall@5 / MRR on the fixture | Encode ms / 32 chunks | Compare vectors across models |
| Reranker | NDCG@5 / accuracy of gold chunk in top-3 | Predict ms / 20 pairs | Claim a win on one query |

The failed 1.5B LoRA stays `experimental: true`. None of these candidates become `selectable_default` until RESULTS.md says so.

---

## Hardware note

Colab T4 p95 from the LoRA eval is **not** this laptop’s GGUF p95. Time every GGUF run on the machine that will serve it.
