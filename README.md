# LearnMateAI

[![Deploy Application](https://github.com/LearnMateAI/project/actions/workflows/deploy.yml/badge.svg)](https://github.com/LearnMateAI/project/actions/workflows/deploy.yml)

Offline-first study assistant for Sri Lankan legal education. Upload lecture notes, ask
questions that cite the pages they came from, and generate summaries, key points, MCQs, and
practice questions. A **second model** grades what the first wrote before you see it.

Nothing you upload leaves the machine. Models run locally through llama.cpp. MongoDB and
Qdrant run in Docker beside the API.

**Live app:** `integrated-frontend` + `integrated-backend`  
**Offline ML track:** `model-Thevindu/` (dataset → LoRA → eval → promote a pointer)

Semester 5 group project. Changes land on feature branches and pull requests into `main`.

---

## What it does

| You do | LearnMate does |
| --- | --- |
| Upload a PDF, Word (`.docx`), PowerPoint (`.pptx`), or LaTeX (`.tex`) | Extract, clean, chunk, embed. The file is **Ready** when chat and generate can use it. |
| Ask a question in Chat | Retrieve the best passages, answer from them, cite pages, then the judge scores the reply. |
| Generate study material | Summary, key points, MCQs, or short-answer practice — one passage or the whole document. |
| Open Analytics | Your activity, judge scores, and (if enabled) a class heatmap of confusing pages. |

Limits: 10 MB, 300 pages. Older `.doc` / `.ppt` files are not accepted — save them as
`.docx` / `.pptx`. The same file uploaded twice is stored once (SHA-256).

---

## How it is put together

```
Browser (React / Vite :5173)
        │  JWT + JSON
        ▼
FastAPI (server.py :8010)
        │  202 job  →  one worker thread
        ▼
learnmate/ engine
   ingest → Qdrant + BM25
   chat:    rewrite → retrieve → generate → evaluate → persist
   resources: generate → Gate 1 (structure) → Gate 2 (LLM judge)

MongoDB :27018     files, accounts, history, jobs
Qdrant  :6335      chunk vectors
GGUFs   ~4 GB      Qwen 2.5 3B writes · Llama 3.2 3B grades
```

`learnmate/` is the engine: it does not know about HTTP or users. `app/` is the web layer:
accounts, access control, routers, and the job queue. A router never talks to the database
directly; a service never raises `HTTPException`.

The generator and the judge are **different model families** on purpose. A model grading
its own writing will praise its own style.

---

## Repository

| Path | What it is |
| --- | --- |
| [`integrated-backend/`](integrated-backend/README.md) | FastAPI + `learnmate/` engine, Docker Compose, smoke tests |
| [`integrated-frontend/`](integrated-frontend/README.md) | React app: documents, chat, resources, analytics |
| [`model-Thevindu/`](model-Thevindu/README.md) | Offline corpus, LoRA runs, eval, promotion gate |
| [`testing/`](testing/README.md) | Unit, integration, and UAT suites |
| [`paper/`](paper/) | Demo / IEEE paper sources |
| [`screenshots/`](screenshots/) | UI and stack captures |
| [`IMPROVEMENTS.md`](IMPROVEMENTS.md) | Classroom-scale extras (hybrid search, cache, workers, heatmap) |

---

## Requirements

| | |
| --- | --- |
| Python | 3.13 |
| Node | 18+ |
| Docker | MongoDB and Qdrant |
| Disk | ~4 GB for the two GGUFs, plus your files |
| RAM | 8 GB works; 16 GB is comfortable |

No API keys after the models have downloaded. Port **8010** for the API (not 8000) and
**5173** for Vite. Mongo is on **27018**, Qdrant on **6335**, so they do not collide with
other projects on this machine.

---

## Run it

### 1. Databases

```bash
cd integrated-backend
docker compose up -d
```

### 2. Backend

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python -c "import secrets; print(secrets.token_hex(32))"
```

Paste that hex into `JWT_SECRET_KEY` in `.env`. Then:

```bash
python -m uvicorn server:app --reload --port 8010
```

On macOS / Linux use `source venv/bin/activate` and `cp .env.example .env`.

Open <http://localhost:8010/api/health>. It should say `ok` with both databases reachable.
Interactive API docs: <http://localhost:8010/docs>.

The GGUFs (~4 GB) download on first use.

### 3. Frontend

In a second terminal:

```bash
cd integrated-frontend
npm install
copy .env.example .env
npm run dev
```

Open <http://localhost:5173>. Register, upload a document, wait until it is **Ready**, then
chat or generate. If Vite picks another port, add that origin to `FRONTEND_ORIGIN` in the
backend `.env` or CORS will block every request.

### 4. Optional smoke test

```bash
cd integrated-backend
venv\Scripts\python scripts\smoke_test.py data\Company-law-part1-notes.pdf --base-url http://127.0.0.1:8010
```

That registers a throwaway account, uploads, ingests, generates, chats, and reads analytics.
`--fast` skips the judge.

---

## Models (live vs offline)

| Role | Default | Notes |
| --- | --- | --- |
| Generator | Qwen2.5-3B-Instruct Q4 GGUF | Writes replies and study material |
| Judge | Llama-3.2-3B-Instruct Q4 GGUF | Grades the generator |
| Embeddings | `all-MiniLM-L6-v2` | Chunk and query vectors |
| Reranker | `ms-marco-MiniLM-L-6-v2` | Reorders the top retrieved chunks |

The offline track in `model-Thevindu/` built a legal LoRA
(`qwen25-lora-20260815-090709`). It **failed the promotion gate**. Do not point the app at
it. Keep the stock generator and the API fallback.

To use a GPU, set `LEARNMATE_N_GPU_LAYERS=-1` in `integrated-backend/.env` and install
`llama-cpp-python` built for that GPU. `API_WARM_MODELS=1` loads both GGUFs at boot so the
first student does not wait.

---

## Classroom extras (off until you turn them on)

[`IMPROVEMENTS.md`](IMPROVEMENTS.md) covers four optional features for a shared lecture
file:

1. Hybrid keyword + meaning search  
2. Answer cache for a repeated, already-judged question  
3. More than one worker  
4. Class confusion heatmap  

Defaults match the single-student laptop path. Change them only in `.env`.

---

## More documentation

| Document | Covers |
| --- | --- |
| [integrated-backend/README.md](integrated-backend/README.md) | Layout, config, endpoints, troubleshooting |
| [integrated-frontend/README.md](integrated-frontend/README.md) | Pages, jobs, citations, quality badges |
| [model-Thevindu/README.md](model-Thevindu/README.md) | Dataset lineage, training log, honesty board |
| [testing/README.md](testing/README.md) | How to run unit, integration, and UAT tests |
| [IMPROVEMENTS.md](IMPROVEMENTS.md) | What each classroom flag does |
