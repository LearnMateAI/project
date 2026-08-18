# LearnMateAI — `model-Thevindu` full workflow and branch inventory

**Audience:** teammates and evaluators checking out `thevindu-dev`.  
**Branch:** `thevindu-dev` only. This snapshot is **not** for `main`. A PR into `main` would drag large PDFs and a LoRA adapter with it unless those paths are taken out first.  
**Status of the candidate:** `qwen25-lora-20260815-090709` on `lm-legal-v0.1` — **failed the promotion gate**. Do not load it in the live app.

This track is **offline**. `integrated-frontend` and `integrated-backend` do not import this folder. Training and eval never run inside a student chat request.

---

## How to read this folder

```
model-Thevindu/
├── 01_dataset_pipeline/     corpus → chunks → pairs → train/val/test
├── 02_finetuning/           Colab LoRA notebook + run-records + (this branch) one adapter
├── 03_testing_and_versioning/  accuracy / groundedness / latency / fallback registry
├── 04_docs/                 lineage, model card, this inventory, mentor note
└── 05_mlops_workflow/       retrain → eval → stage → promote → rollback (process only)
```

Start here, then `README.md` in this folder, then `version_registry.csv`.

---

## Step 0 — Security (done as a rule, still your job for the leaked key)

An API key was pasted into chat during dataset work. A pasted key is compromised. Rotate it at the provider console. Store the replacement only in a **gitignored** `.env`, loaded with `python-dotenv`. Never pass it as a CLI argument or notebook cell.

| Path | In git? |
|------|---------|
| `01_dataset_pipeline/.env` | **No** — ignored (`*.env`, `**/.env`) |
| `01_dataset_pipeline/.env.example` | **Yes** — variable names only |

---

## Step 1 — Corpus and Stage 1 parse

**Input:** Sri Lankan legal PDFs/HTML listed in `01_dataset_pipeline/manifests/target_corpus_manifest.csv`. Subject tags come from that CSV, not from filename guessing.

**On this branch (newly tracked for evaluation):** `01_dataset_pipeline/data/raw_pdfs/` — the 21 files used for `lm-legal-v0.1`, including two scans that failed Stage 1.

**Excluded (also tracked, so the decision is visible):** `data/excluded_from_corpus/Black's-Law-4th-edition-1891.pdf` plus `WHY_EXCLUDED.md`. It is an 1891 American dictionary, not Sri Lankan law.

Stage 1 (`preprocess_dataset.py`): extract text, drop TOC fragments, chunk with inherited `section_id`, tag `subject_area` from the manifest.

| Stage 1 result | Number |
|----------------|--------|
| Files in `raw_pdfs/` | 21 |
| Parsed OK | **19** |
| Failed (no text layer) | **2** — `Arbitration act 2.pdf` (~35 MB scan), `Mediation Boards Act no 27.pdf` (~21 MB scan) |
| Chunks | **1,280** (52 TOC chunks dropped) |
| Subject from manifest / from filename fallback | **21 / 0** |

Cleaned text of the 19 successes: `processed_v01/cleaned_text/`. Chunks: `processed_v01/chunks.jsonl`.

---

## Step 2 — Training pairs (GI-001)

Stage 2 (`generate_training_pairs.py`) asks `gpt-4o-mini` for two pairs per chunk (Q&A / summary / MCQ) grounded in the excerpt.

**Bug GI-001:** a 40-pair spot check found ~38% ungrounded section citations. Fix: TOC drop, inherit `section_id`, citation rule in the prompt, fail-closed `validate_pairs.py`.

**After the fix (full corpus):** 2,534 pairs kept, **26 rejected (1.0%)**, 0 API errors. See `processed_v01/pairs.jsonl` and `pairs.summary.json`.

---

## Step 3 — Split (GI-002)

Whole-document split was unusable: `family_law` and `property_land` had **zero** training pairs.

**Fix:** group by `(doc_id, chapter)` and keep a small true document holdout.

| Split | File | Count | Metric name |
|-------|------|-------|-------------|
| train | `processed_v01/train.jsonl` | 1,590 | (training) |
| val | `processed_v01/val.jsonl` | 339 | (training) |
| test | `processed_v01/test.jsonl` | 325 | `in_corpus_accuracy (chapter-held-out)` |
| test_strict | `processed_v01/test_strict.jsonl` | 280 | `accuracy (document-held-out)` |

All 11 subjects that appear in the parsed corpus are in train, val, and test. `test_strict` only covers subjects with enough documents: civil_procedure, constitutional_law, contract_law, criminal_procedure.

**No true generalisation test until a second source document exists:** `administrative_public`, `company_commercial`, `criminal_law`, `evidence`, `intellectual_property`, `property_land`. `family_law` has two documents but still no strict holdout (holding one out leaves a single unit).

---

## Step 4 — Fine-tune (Qwen LoRA)

Notebook: `02_finetuning/finetune_qwen25_lora.ipynb` on Colab T4.

| | Smoke 1 | Smoke 2 | **Real candidate** |
|--|---------|---------|---------------------|
| run_id | `qwen25-lora-20260810-052502` | `qwen25-lora-20260813-054543` | **`qwen25-lora-20260815-090709`** |
| dataset | synthetic smoke-v1 | synthetic smoke-v2 | **`lm-legal-v0.1`** |
| train / val | 69 / 15 | 46 / 10 | **1,590 / 339** |
| epochs / steps | smoke | smoke | **3 / 597** |
| train / eval loss | — | — | **1.038 / 1.247** |
| hardware | T4 | T4 | T4, peak **3.39 / 14.6 GB**, ~94 min |
| promote? | No | No | **No** |

LoRA: r=16, alpha=32, QLoRA 4-bit, Qwen2.5-1.5B-Instruct.

**On this branch:** `02_finetuning/adapters/qwen25-lora-20260815-090709/adapter/` including `adapter_model.safetensors` (~70 MB) and `adapter_config.json`. Smoke adapters and all `checkpoints/` stay **local / gitignored**.

Run record (always tracked): `02_finetuning/run_records/qwen25-lora-20260815-090709.json`.

---

## Step 5 — Evaluate (Qwen tests)

Notebook: `03_testing_and_versioning/evaluate_candidate.ipynb` (`dry_run: false`).  
Offline re-score: `rescore_eval.py` (groundedness via `validate_pairs`) and `--llm-judge` (accuracy).

**Predictions (already on the branch):**

- `eval_predictions/qwen25-lora-20260815-090709_test.jsonl` (325)
- `eval_predictions/qwen25-lora-20260815-090709_test_strict.jsonl` (280)

Contract: `acceptance_thresholds.yaml` v2 — accuracy ≥ 0.70, groundedness ≥ 0.85, hallucination ≤ 0.15, p95 latency ≤ 8 s on named hardware, must compare to a fallback API.

### Registry result (do not promote)

| Metric | chapter `test` | strict `test_strict` |
|--------|----------------|----------------------|
| Accuracy token-F1 (proxy) | 0.717 | 0.836 |
| **Accuracy LLM-as-judge (`gpt-4o-mini`)** | **0.557** | **0.621** |
| Groundedness (naive regex, first pass) | 0.498 | 0.586 |
| **Groundedness (`validate_pairs`)** | **0.877** | **0.921** |
| Latency p95 | 16.4 s | 14.9 s |
| vs gpt-4o-mini token-F1 | 0.717 vs 0.871 | 0.836 vs 0.918 |
| `passed` | **False** | **False** |

Token-F1 overstated correctness. The judge number is the one that matches the live “unsupported claim = fail” idea. Groundedness PASS after the regex bug was removed. Remaining real fails: **accuracy (judge)**, **T4 latency**, **does not beat the API**.

Fallback on this eval was **gpt-4o-mini**, not Gemini. Fallback accuracy in the last registry rows is still token-F1, so “vs fallback” mixes two graders.

---

## Step 6 — Promotion (not done)

`03_testing_and_versioning/promotion_checklist.md` — staging, second-person sign-off, production pointer, rollback. **Blocked.** The live app keeps local Qwen 2.5-3B GGUF + optional API.

---

## What is on `thevindu-dev` vs what `.gitignore` still hides

### Tracked on this branch (including evaluation force-adds)

| What | Where |
|------|--------|
| Pipeline code, manifest, sample PDFs | `01_dataset_pipeline/` |
| **Real corpus PDFs/HTML** | `data/raw_pdfs/` |
| **Excluded dictionary + reason** | `data/excluded_from_corpus/` |
| **Full `lm-legal-v0.1` processed set** | `processed_v01/` (chunks, pairs, train/val/test/test_strict, cleaned_text, reports) |
| Finetune notebook + run-records | `02_finetuning/` |
| **Real LoRA adapter (v0.1 only)** | `adapters/qwen25-lora-20260815-090709/adapter/` |
| Eval notebook, thresholds, registry, predictions | `03_testing_and_versioning/` |
| Lineage, model card, mentor note, this file | `04_docs/` |
| MLOps lifecycle (doc only) | `05_mlops_workflow/` |
| Root index README (after merge with `main`) | repo `README.md` |

### Still gitignored / not pushed (on purpose)

| What | Why |
|------|-----|
| `**/.env`, `*.env` | Secrets |
| Smoke `processed/` and `processed_real/` | Not the evaluation corpus; v0.1 is `processed_v01/` |
| Smoke adapters `20260810` / `20260813` | Synthetic runs |
| `**/checkpoints/` | Duplicate ~70 MB files per step |
| `tokenizer.json` in the adapter folder | ~11 MB; load tokenizer from `Qwen/Qwen2.5-1.5B-Instruct` |
| `03_testing_and_versioning/New/` | Contains a large `adapter.zip` |
| `*.zip`, `*.log`, `models/` (GGUFs for the live app) | Noise / 4 GB local models |
| Intermediate `data/intermediate/`, `data/output/` | Regenerable |

`.gitignore` still lists `raw_pdfs/*`, `processed*/`, `adapters/`, and `*.safetensors` so a careless add on another machine does not pick up secrets or extra weights. This evaluation snapshot was **`git add -f`** on `thevindu-dev` only.

---

## What `main` has vs this branch

`main` has the student app (`integrated-frontend` + `integrated-backend`) and does **not** need this corpus or adapter to run. `thevindu-dev` already merged `origin/main` (conflict resolution on `.gitignore` and the README split). Merging **this** branch back to `main` without stripping the force-added binaries would put ~150 MB+ of statutes and a LoRA file on the integration branch. Do not do that unless the team agrees.

---

## Not integrated into the application

The live path is: React → FastAPI (`learnmate/` engine) → local **Qwen2.5-3B** GGUF + **Llama-3.2-3B** judge + Qdrant. Slow work is a job queue.

This LoRA is a **1.5B** domain adapter. Pointing the app at it is two `.env` lines (`LEARNMATE_GENERATOR_BACKEND=http` or a served adapter) **after** a genuine gate pass. That has not happened. Wiring it in now would add GPU/Colab-class work to the request path for a model that lost the accuracy and latency gates.

---

## Future work

1. Keep v0.1 frozen. Cut **`lm-legal-v0.2`** with ≥2 (ideally 3) text-layer documents per subject so `test_strict` covers the single-doc gaps. Use replacements already found for Arbitration and Mediation Boards; add RTI, IP amendment, Bail Act, SC judgments from the existing manifest.
2. Diagnose the 0.557 / 0.621 judge fails on the **saved** predictions before any second training run.
3. Optional: LLM-as-judge on the saved **fallback** answers so the comparison uses one grader.
4. Mentor disclosure: `mentor_pilot_disclosure.md` (update the table to the judge numbers).
5. Promote only through the checklist, on document-held-out pass, signed by someone who did not train the run.

---

## Quick numbers for a viva / evaluation

| Item | Value |
|------|--------|
| Dataset | `lm-legal-v0.1` |
| Parsed docs / chunks / pairs | 19 / 1,280 / 2,534 |
| Train / val / test / strict | 1,590 / 339 / 325 / 280 |
| Base + method | Qwen2.5-1.5B-Instruct, LoRA r=16, QLoRA, 3 epochs |
| Candidate | `qwen25-lora-20260815-090709` |
| Judge accuracy | 0.557 (chapter) / 0.621 (strict) — **below 0.70** |
| Groundedness (`validate_pairs`) | 0.877 / 0.921 — **above 0.85** |
| Promote | **No** |
