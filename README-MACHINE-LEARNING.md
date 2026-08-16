# LearnMateAI — models, retrieval, evaluation

Two separate ML stories share this repository. They must not be confused.

| Path | When it runs | What it is |
|---|---|---|
| **Live** (`integrated-backend/learnmate/`) | Every chat / resource request | Local GGUF generator + a different-family judge + RAG |
| **Offline** (`model-Thevindu/`) | Manual Colab / scripts, never in the request path | LoRA fine-tune of Qwen 2.5 on Sri Lankan legal text, then a promotion gate |

Swapping the live generator for a served finetune or a cloud API is two lines in
`integrated-backend/.env` and no code change. That pointer is the only thing the app
should learn from the offline track.

Companion docs: [README-APPLICATION.md](README-APPLICATION.md) (software shape),
[README-USAGE.md](README-USAGE.md) (how to run it),
[README-TECHNOLOGIES.md](README-TECHNOLOGIES.md) (library list).

---

## 1. Live models

| Role | Model | Why |
|---|---|---|
| Generator | Qwen2.5-3B-Instruct (Q4 GGUF) | Writes chat replies and study material |
| Judge | Llama-3.2-3B-Instruct (Q4 GGUF) | Grades the generator; different family on purpose |
| Embeddings | `all-MiniLM-L6-v2` | Chunk and query vectors |
| Reranker | `ms-marco-MiniLM-L-6-v2` | Reorders the top retrieved chunks with the question |

The judge is a different family so it cannot just praise its own style. Q4 quantisation
is what makes both 3B models fit a laptop.

Optional and off by default: Gemini (`google-genai`) if `.env` points the generator or
fallback at a cloud API.

---

## 2. Retrieval and the chat graph

A chat turn is one LangGraph pass:

`rewrite → retrieve → generate → evaluate → decide → persist`

- **Retrieve:** embed the question, nearest chunks in Qdrant, then cross-encoder rerank.
- **Generate:** answer from those chunks. The live Verification Agent treats a claim not
  supported by retrieved context as a hallucination.
- **Evaluate / decide:** structural checks, then the judge. One retry on the same
  generator if the judge rejects; the live path does **not** silently swap in Gemini
  because an answer scored poorly. Gemini (or another API) is an *availability*
  fallback — process down, timeout, missing pointer — not a per-answer quality router.

Resource generation (summary, MCQ, keypoints, practice questions) is a second graph in
`learnmate/resource_agent/`. Same rule: grounded in the uploaded PDF, then judged.

---

## 3. Offline domain fine-tune (`model-Thevindu/`)

```
Sri Lankan legal PDFs
        → Stage 1  parse / clean / section-aware chunks
        → Stage 2  instruction pairs (Q&A, summary, MCQ)
        → Stage 3  chapter-group train/val/test + a small whole-document holdout
        → LoRA / QLoRA on Qwen2.5-1.5B-Instruct (Colab T4)
        → Eval vs acceptance_thresholds.yaml + fallback comparison
        → staging → teammate sign-off → promote a live pointer → rollback kept
```

| Part | Path |
|---|---|
| Pipeline | `model-Thevindu/01_dataset_pipeline/` |
| Fine-tune notebook | `model-Thevindu/02_finetuning/finetune_qwen25_lora.ipynb` |
| Eval, registry, checklist | `model-Thevindu/03_testing_and_versioning/` |
| Lineage, training log, mentor note | `model-Thevindu/04_docs/` |
| Promote / rollback process | `model-Thevindu/05_mlops_workflow/` |

Weights (`*.safetensors`, adapters, checkpoints) are gitignored. The auditable record of
a run is `02_finetuning/run_records/<run_id>.json`.

### Dataset issues already found

- **GI-001** — Stage 2 was writing ungrounded section citations (~38% on a spot check).
  Fixed in the generator + `validate_pairs.py`. Full-corpus reject rate after the fix: 1.0%.
- **GI-002** — Whole-document split left subjects with zero training pairs. Split is now
  by `(doc_id, chapter)`. That number is **`in_corpus_accuracy (chapter-held-out)`**, not
  true generalisation. `test_strict.jsonl` holds out one full document per multi-document
  subject (`accuracy (document-held-out)`). Six subjects still have only one source
  document, so they have no true generalisation test until the corpus grows.

Pilot corpus: 21 files ingested, 19 parsed; 13 Tier A / 19 Tier B in the target manifest.
See `04_docs/mentor_pilot_disclosure.md`.

### First real candidate — do not promote

`qwen25-lora-20260815-090709` on `lm-legal-v0.1` (1590 train / 339 val). Logged in
`version_registry.csv`. Both splits **FAIL**.

| Metric | chapter `test` | strict `test_strict` | Gate |
|---|---|---|---|
| Accuracy (token-F1, proxy) | 0.717 | 0.836 | looked like a pass |
| Accuracy (LLM-as-judge, `gpt-4o-mini`) | **0.557** | **0.621** | ≥ 0.70 — **fail** |
| Groundedness (`validate_pairs`) | 0.877 | 0.921 | ≥ 0.85 — pass |
| Hallucination | 0.123 | 0.079 | ≤ 0.15 — pass |
| Latency p95 | 16.4 s | 14.9 s | ≤ 8 s — fail (Colab T4 sequential 4-bit, not serving hardware) |
| vs gpt-4o-mini (token-F1) | 0.717 vs 0.871 | 0.836 vs 0.918 | lose |

Token-F1 overstated correctness. The judge that matches the live “unsupported claim =
fail” idea is the number to read. Keep the API / local GGUF as the live generator. Treat
this adapter as a pilot, not a replacement.

Promotion requires `passed=True` on **document-held-out**, a filled
`promotion_checklist.md`, and a teammate who did not train the run. None of that is done.

---

## 4. What “evaluation” means in each path

| | Live app | Offline gate |
|---|---|---|
| Correctness | Llama 3.2 judge + structural validators | LLM-as-judge preferred; token-F1 only if no judge API |
| Groundedness | Claim must be supported by retrieved chunks | Same citation checker as Stage 2 (`validate_pairs.py`) |
| Fallback | Availability (down / timeout / no pointer) | Candidate must beat or nearly match the configured API on the same test set |

If those two groundedness definitions diverge, a green offline gate says nothing about
production behaviour. The current contract is in
`model-Thevindu/03_testing_and_versioning/acceptance_thresholds.yaml` (version 2).
