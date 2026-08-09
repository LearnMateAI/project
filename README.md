# LearnMateAI

**AI-powered study platform for Sri Lankan legal education.**

Upload lecture or statute PDFs → the system extracts and indexes the content → students get grounded chat Q&A plus generated study resources (summaries, MCQs, keypoints, practice questions). A domain-specific **Qwen 2.5** path (LoRA fine-tuning track) can replace or sit beside a general generator, with graceful fallback if the custom model is unavailable.

Semester 5 group project — e-learning platform using large language models.

---

## What it does

| Capability | Description |
|------------|-------------|
| PDF study ingest | Validate, store, clean, chunk, and embed course / legal PDFs |
| Grounded chat | RAG over the uploaded document (retrieve relevant chunks, then answer) |
| Study resources | Summaries, multiple-choice questions, keypoints, short practice questions |
| Quality gate | A separate *judge* model scores generated resources and can trigger one retry |
| Domain model track | Offline pipeline to fine-tune Qwen 2.5 on Sri Lankan legal corpora (LoRA/PEFT) |
| Degradation | App must keep working via general / HTTP API fallback if a fine-tuned adapter is down |

**Primary domain focus:** Sri Lankan legal education (statutes, codes, procedure, evidence, case method, etc.), while the ingest/chat/resource pipeline is PDF-general.

---

## High-level architecture

```
                    ┌──────────────────────────────────────────┐
  Student (React) ──┤  Frontend (Vite)                         │
                    └──────────────────┬───────────────────────┘
                                       │ HTTP / JWT (evolving)
                    ┌──────────────────▼───────────────────────┐
                    │  App / agents                             │
                    │  ingest → chat (RAG) → resource gen      │
                    │  → evaluator (judge + retry)             │
                    └───────────┬──────────────────┬───────────┘
                                │                  │
                     ┌──────────▼──────┐   ┌───────▼────────┐
                     │ MongoDB         │   │ Qdrant         │
                     │ PDFs, pages,    │   │ chunk vectors  │
                     │ sessions, chat, │   │                │
                     │ resources       │   │                │
                     └─────────────────┘   └────────────────┘
                                       │
                     ┌─────────────────▼─────────────────────┐
                     │ Generator LLM (Qwen 2.5 local GGUF    │
                     │   or HTTP → promoted fine-tuned model)│
                     │ Judge LLM (Llama 3.2 — different      │
                     │   family on purpose)                  │
                     │ Embeddings (all-MiniLM-L6-v2)         │
                     └───────────────────────────────────────┘

  OFFLINE (not in the request path)
  model-Thevindu: corpus → pairs → LoRA train → eval → promote live pointer
```

The fine-tuning / MLOps cycle is **manual or scheduled**. The live app only needs to know which generator version (or HTTP endpoint) is live — not how it was trained. See [`model-Thevindu/05_mlops_workflow/`](model-Thevindu/05_mlops_workflow/).

---

## Repository layout

```
project/
├── README.md                 ← this file
├── docs/                     ← project plans / diagrams
├── components-Dinura/        ← main local LearnMate agent stack (ingest, chat, resources, eval)
├── backend/                  ← FastAPI-oriented backend scaffold / services (evolving)
├── frontend/                 ← React (Vite) UI scaffold
└── model-Thevindu/           ← offline ML / domain fine-tuning track
```

| Folder | Owner focus | Start here |
|--------|-------------|------------|
| [`components-Dinura/`](components-Dinura/README.md) | Local multi-agent study assistant (CLI + guided program) | Full README + `cli.py doctor` |
| [`backend/`](backend/README.md) | FastAPI / service wiring | `venv` + `requirements.txt` |
| [`frontend/`](frontend/README.md) | React UI | `npm run dev` |
| [`model-Thevindu/`](model-Thevindu/README.md) | Dataset pipeline, LoRA, eval, model card, MLOps | Honesty board in that README |

Teammate frontend/auth work may also live on branch `tharumini-dev` before it is merged to `main`.

---

## Tech stack

| Layer | Technologies |
|-------|----------------|
| Frontend | React, Vite |
| Backend / agents | Python, FastAPI (scaffold), LangChain-oriented agent code in `components-Dinura` |
| Data | MongoDB (documents, sessions, history, resources), Qdrant (vectors) |
| Generator | Qwen2.5-Instruct (local GGUF via llama.cpp, or HTTP OpenAI-compatible API) |
| Judge | Llama-3.2-Instruct (separate family for evaluation) |
| Embeddings | `all-MiniLM-L6-v2` (Hugging Face) |
| Domain fine-tune | Qwen 2.5 + LoRA/PEFT (Colab notebook in `model-Thevindu/02_finetuning/`) |
| Ops | Docker Compose (Mongo + Qdrant), GitHub branches per contributor |

---

## Quick start

### A. Local study assistant (`components-Dinura`) — primary runnable path today

```bash
cd components-Dinura

python -m venv venv
# Windows:
venv\Scripts\pip install -r requirements.txt
# macOS/Linux:
# source venv/bin/activate && pip install -r requirements.txt

docker compose up -d          # MongoDB :27018, Qdrant :6335
venv\Scripts\python cli.py doctor

# Ingest a PDF into a session, then chat / generate resources:
venv\Scripts\python cli.py ingest data\constitution.pdf --session s1
# or guided walkthrough:
python learnmate\full_program.py
```

Copy [`components-Dinura/.env.example`](components-Dinura/.env.example) → `.env` if you need to change ports, backends, or point the **generator** at a fine-tuned HTTP endpoint:

```env
LEARNMATE_GENERATOR_BACKEND=http
LEARNMATE_GENERATOR_API_URL=http://localhost:8001/v1
LEARNMATE_GENERATOR_MODEL=learnmate-finetuned
```

Expect CPU inference to be slow (tens of seconds per turn). See the [components-Dinura README](components-Dinura/README.md) for the full workflow.

### B. Frontend scaffold

```bash
cd frontend
npm install
npm run dev
```

### C. Backend scaffold

```bash
cd backend
python -m venv venv
# activate venv, then:
pip install -r requirements.txt
```

See [`backend/README.md`](backend/README.md).

### D. Domain model track (`model-Thevindu`)

Offline only — does not run inside chat requests.

```bash
cd model-Thevindu/01_dataset_pipeline
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

# Smoke test (no API cost):
python scripts/run_pipeline.py --create-samples --mock --dataset-version lm-legal-smoke-v1

# Real corpus (after placing PDFs under data/raw_pdfs/):
python preprocess_dataset.py --input_dir data/raw_pdfs --output_dir processed
# then generate_training_pairs.py / split_dataset.py — see folder README
```

Fine-tune: open [`model-Thevindu/02_finetuning/finetune_qwen25_lora.ipynb`](model-Thevindu/02_finetuning/finetune_qwen25_lora.ipynb) on Colab (GPU).  
Evaluate / promote: [`model-Thevindu/03_testing_and_versioning/`](model-Thevindu/03_testing_and_versioning/).

**Secrets:** use `.env` files (gitignored). Never commit API keys. `.env.example` files show required variable names only.

---

## Domain fine-tuning track (summary)

```
Sri Lankan legal PDFs
        → Stage 1  parse / clean / semantic chunk (section-aware)
        → Stage 2  instruction pairs (Q&A, summary, MCQ) — mock or live LLM
        → Stage 3  whole-document train/val/test split + subject balance report
        → LoRA fine-tune Qwen 2.5 (mandatory run-record)
        → Eval vs thresholds + fallback comparison
        → Stage → promote live pointer → monitor → rollback
```

| Part | Path |
|------|------|
| Pipeline | `model-Thevindu/01_dataset_pipeline/` |
| Fine-tune notebook | `model-Thevindu/02_finetuning/` |
| Eval + registry + checklist | `model-Thevindu/03_testing_and_versioning/` |
| Model card / lineage / training log | `model-Thevindu/04_docs/` |
| MLOps lifecycle | `model-Thevindu/05_mlops_workflow/` |

Target corpus listings (verified free portals):  
`model-Thevindu/01_dataset_pipeline/manifests/target_corpus_manifest.csv`

What has been executed vs what is still a template is stated honestly in  
[`model-Thevindu/README.md`](model-Thevindu/README.md) — treat that board as source of truth before claiming a production model.

---

## Team & branches

| Branch | Role (typical) |
|--------|----------------|
| `main` | Integration / merged work |
| `dinura-dev` | Agent stack, local inference, resources, evaluator |
| `tharumini-dev` | Frontend, auth, upload UX (merge status varies) |
| `thevindu-dev` | Domain model / fine-tuning track (`model-Thevindu/`) |

```bash
git fetch origin
git checkout thevindu-dev    # example
git pull origin main         # keep up to date before large merges
```

---

## Project goals (course framing)

From the module brief / plan docs:

1. Select suitable LLMs and implement a pipeline that generates educational resources from PDFs.  
2. Deliver a web application (React + FastAPI + MongoDB) demonstrating the workflow.  
3. Meet reasonable accuracy and operational performance.  
4. Document each stage of implementation.

Supporting resource types include lecture summaries, concept explanations, flashcards/MCQs, short-answer practice, and AI Q&A chat — scoped to what the uploaded material supports.

---

## Documentation map

| Doc | Contents |
|-----|----------|
| [components-Dinura/README.md](components-Dinura/README.md) | End-to-end local assistant: ingest, chat, resources, judge, config |
| [model-Thevindu/README.md](model-Thevindu/README.md) | Fine-tuning track honesty board + layout |
| [model-Thevindu/05_mlops_workflow/mlops_lifecycle.md](model-Thevindu/05_mlops_workflow/mlops_lifecycle.md) | Retrain → evaluate → stage → promote → monitor → rollback |
| [model-Thevindu/04_docs/model_card.md](model-Thevindu/04_docs/model_card.md) | Intended use, limitations, ethics |
| [docs/](docs/) | Early plans and diagrams |
| [frontend/README.md](frontend/README.md) / [backend/README.md](backend/README.md) | Scaffold run notes |

---

## Design principles

1. **Ground answers in the document** when retrieval is strong; don’t invent statutory citations.  
2. **Separate generator and judge** so self-scoring doesn’t silently pass bad output.  
3. **One PDF per session** by default in the local stack (embedding is expensive).  
4. **Offline ML ≠ request path** — training and promotion stay outside live chat.  
5. **Fail open to a general model / API** if the domain adapter is missing, cold, or over quota.  
6. **Budget-aware** — student team ops (~USD 45/month): prefer small Qwen + QLoRA / local GGUF over always-on large cloud models.

---

## License & academic use

Course project for educational purposes. Legal source texts remain under their respective official / database terms (CommonLII, Parliament, government printer, etc.). Generated study aids are **not legal advice**.

---

## Maintainers

Group project — LearnMateAI. Contributions land via feature branches and pull requests into `main`.
