# 05 — MLOps workflow (offline)

LearnMateAI’s domain model lifecycle is a **manual / scheduled offline process**.  
It is **not** wired into the live application’s request path. The app only needs to know which model version is currently live (plus how to reach the API fallback).

```
 ┌─────────────────────────────────────────────────────────────┐
 │  OFFLINE / SCHEDULED (this folder)                          │
 │                                                             │
 │  retrain → evaluate → stage → promote → monitor → rollback  │
 │                                                             │
 └───────────────────────────┬─────────────────────────────────┘
                             │ writes live_model_version pointer
                             ▼
 ┌─────────────────────────────────────────────────────────────┐
 │  ONLINE APP (React + FastAPI + MongoDB + Qdrant)            │
 │                                                             │
 │  request → retrieve (Qdrant) → try live adapter             │
 │                         └─ on miss/error → Gemini fallback  │
 └─────────────────────────────────────────────────────────────┘
```

---

## 1. Retrain (scheduled or triggered manually)

**When:** new statutes downloaded, dataset regenerated, or quarterly refresh — **not** per user chat.

1. Update / download PDFs; refresh run manifest.
2. Run `01_dataset_pipeline` → new `dataset_version`.
3. Check Stage 3 subject-balance warnings; fix corpus gaps before training if val/test lack a subject you care about.
4. Run `02_finetuning/finetune_qwen25_lora.ipynb` on Colab (LoRA/QLoRA).
5. Ensure the mandatory **run-record** cell executed.
6. Log cost/duration in `04_docs/training_run_log.md`.

**Not in the request path:** no training jobs spawn from FastAPI handlers.

---

## 2. Evaluate

1. Open `03_testing_and_versioning/evaluate_candidate.ipynb` with `dry_run: false`.
2. Score held-out **test** split against `acceptance_thresholds.yaml`.
3. Mandatory comparison vs Gemini (or configured) fallback.
4. Append row to `version_registry.csv` (pass or fail).

Fail-closed: any missed threshold or missing fallback comparison ⇒ stop.

---

## 3. Stage

1. Copy adapter artifact to the team’s staging store.
2. Point **staging** `live_model_version` at the candidate (production unchanged).
3. Smoke-test Q&A / MCQ / insufficient-excerpt behaviour.
4. Confirm killing the adapter still serves answers via fallback.

---

## 4. Promote

1. Complete every step in `promotion_checklist.md` (four-eyes review).
2. Update **production** pointer only:

   ```text
   live_model_version = <candidate run_id>
   ```

3. Record previous version as rollback target.
4. Update `04_docs/dataset_lineage.md` model table.

The React/FastAPI app reads that pointer (env var, Mongo config doc, or secrets store). It does **not** import this MLOps documentation at runtime.

---

## 5. Monitor

First 48 hours after promote, then ongoing weekly:

| Signal | Action if red |
|--------|----------------|
| Fallback invocation rate spike | Check adapter host / timeout settings |
| p95 latency | Scale down max tokens or roll back |
| User-reported hallucination | Spot-check vs sources; roll back if systemic |
| Error rate on adapter route | Fail open to Gemini; file incident |

Monitoring lives in the app/ops stack; this folder only defines the expectation.

---

## 6. Rollback

1. Set `live_model_version` back to the previous registry-passed id (or `null` to force 100% fallback).
2. No retrain required to roll back.
3. Note the rollback in `training_run_log.md` / team chat.
4. Open a new candidate only after root-cause (data vs training vs serving).

---

## Budget & degradation (~USD 45/month ops)

- Prefer small Qwen2.5 + LoRA on free/cheap Colab; Stage 2 drafting on Flash-tier APIs.
- **Never** make the fine-tuned model a single point of failure.
- If the adapter is unavailable, cold, or over-quota → **Gemini (or other general API) fallback**, not an HTTP 500.

---

## What the app is allowed to know

| Allowed | Not allowed / not needed |
|---------|---------------------------|
| `live_model_version` id or URI | Training hyperparameters |
| Fallback model name + API credentials | Dataset pipeline scripts |
| Timeout / retry policy before fallback | Colab notebook paths |
| Feature flag: `use_domain_adapter` | Online retrain triggers |

---

## Cadence (suggested for a 3-person team)

| Activity | Cadence |
|----------|---------|
| Corpus / pipeline smoke | After any pipeline code change |
| Full retrain | When ≥ material new sources land, or exam-term refresh |
| Eval + promote | Only after retrain; never on a schedule that skips thresholds |
| Pointer health check | Weekly |

This document is the process contract; Parts 1–4 are the tooling.
