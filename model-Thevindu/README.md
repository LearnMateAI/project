# model-Thevindu — LearnMateAI ML / fine-tuning track

Offline ML workspace for **LearnMateAI**, an AI study platform for Sri Lankan legal education.

| Stack (main app) | This folder |
|------------------|-------------|
| React + FastAPI + MongoDB | Dataset pipeline, LoRA fine-tune, eval, docs, MLOps |
| Fine-tuned **Qwen 2.5** (domain) | Built and versioned **here** |
| **Gemini API** fallback | Required degradation path if adapter is down |
| **Qdrant** vector DB | Used by the app for RAG — not retrained from request path |

This track is **separate from the live application**. The app should only ever read a `live_model_version` pointer (see `05_mlops_workflow/`).

---

## Honesty board — executed vs template

Full walkthrough for evaluators: [`04_docs/FULL_WORKFLOW_AND_BRANCH_INVENTORY.md`](04_docs/FULL_WORKFLOW_AND_BRANCH_INVENTORY.md).

| Part | Artifact | Executed / tested in this repo? | Notes |
|------|----------|----------------------------------|-------|
| **1** Dataset pipeline | `01_dataset_pipeline/` | **YES — smoke + real v0.1** | Smoke: EXP-001. Real: 21 files → 19 parsed → 1,280 chunks → 2,534 pairs (`lm-legal-v0.1`). On `thevindu-dev`, `data/raw_pdfs/` and `processed_v01/` are tracked for evaluation. |
| **2** Fine-tuning | `02_finetuning/` | **YES — one real Colab run** | `qwen25-lora-20260815-090709` on v0.1 (1,590/339, 3 epochs, T4). Smoke runs exist; do not promote any of them. |
| **3** Testing & versioning | `03_testing_and_versioning/` | **YES — live eval, both splits** | Registry: **FAIL**. LLM-as-judge accuracy 0.557 / 0.621. Groundedness 0.877 / 0.921 after `validate_pairs`. Do not promote. |
| **4** Docs | `04_docs/` | **YES** | Lineage GI-001/002, training log, mentor disclosure, this honesty board. |
| **5** MLOps | `05_mlops_workflow/` | **YES — process doc** | Not wired into FastAPI. App must keep GGUF / API fallback. |

If something is only a correct template, do **not** treat it as a completed training or promotion. The real candidate **failed the gate**.

---

## Layout

```
model-Thevindu/
├── README.md                          ← you are here
├── 01_dataset_pipeline/               ← PDF → chunks → pairs → splits
├── 02_finetuning/                     ← Qwen 2.5 LoRA notebook
├── 03_testing_and_versioning/         ← eval + registry + promotion checklist
├── 04_docs/                           ← model card, training log, lineage
└── 05_mlops_workflow/                 ← offline retrain…rollback cycle
```

---

## Quick start (Part 1 smoke — already proven)

```bash
cd model-Thevindu/01_dataset_pipeline
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
python scripts/run_pipeline.py --create-samples --mock --dataset-version lm-legal-smoke-v1
```

Then open `experiments/EXP-001_smoke_test.md`.

---

## Target legal corpus

`01_dataset_pipeline/manifests/target_corpus_manifest.csv` lists **25** Sri Lankan sources (statutes, codes, case law, official portals) across platform subject areas. URLs were checked against CommonLII, Parliament of Sri Lanka, documents.gov.lk, supremecourt.lk, SriLankaLaw.lk, LankaLaw, and consumeraffairs.gov.lk. Download PDFs before any production training run.

---

## Budget & degradation (~USD 45/month ops)

- Prefer **Qwen2.5-1.5B-Instruct + QLoRA** on free/cheap Colab; cheap APIs for Stage 2 drafting.
- **Never** ship without a general-purpose API fallback (Gemini by default in docs).
- Adapter unavailable ⇒ fallback; not a hard failure.

---

## Suggested order of work for the team

1. Keep Part 1 green (re-run smoke after pipeline edits).
2. Download a subset of the target manifest; cut `lm-legal-v0.1` with `--live` Stage 2 when API budget allows.
3. Run Part 2 on Colab; commit run-record + log cost in `04_docs/training_run_log.md`.
4. Run Part 3 for real; promote only via checklist.
5. Point the FastAPI app at `live_model_version` only — follow Part 5.
