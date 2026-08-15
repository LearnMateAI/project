# LearnMateAI — the application

Upload a PDF. Ask it questions and get answers that cite the pages they came from, or
generate study material from it — summaries, key points, multiple-choice questions and
short-answer practice questions. Everything the system produces is graded by a second
model before it reaches you.

This document describes the **software**: how the pieces fit together and why they are
arranged the way they are. Two companion documents cover the rest:

| Document | Covers |
|---|---|
| `README-USAGE.md` | running it, and using it as a student |
| `README-MACHINE-LEARNING.md` | the models, retrieval, prompting and evaluation |
| `integrated-backend/README.md` | backend detail: layout, configuration, endpoints |

---

## Shape of the system

```
┌────────────────────────┐         ┌──────────────────────────────────────────┐
│   integrated-frontend  │  HTTP   │            integrated-backend            │
│   React 19 + Vite 8    │◄───────►│                                          │
│   Tailwind, React      │  JSON   │   server.py    FastAPI: CORS, routers    │
│   Router               │  + JWT  │   app/         the web layer             │
└────────────────────────┘         │   learnmate/   the engine                │
                                   └───────────────┬──────────────────────────┘
                                                   │
                              ┌────────────────────┼────────────────────┐
                              ▼                    ▼                    ▼
                     ┌────────────────┐   ┌────────────────┐   ┌────────────────┐
                     │    MongoDB     │   │     Qdrant     │   │  Local models  │
                     │     :27018     │   │     :6335      │   │  two GGUFs     │
                     │ PDFs (GridFS), │   │ chunk vectors, │   │  in-process    │
                     │ text, accounts,│   │ HNSW index     │   │  via llama.cpp │
                     │ history, jobs  │   │                │   │                │
                     └────────────────┘   └────────────────┘   └────────────────┘
```

Nothing leaves the machine. The models run locally through `llama.cpp`, and the two
databases run in Docker containers alongside the server.

### Why the ports are unusual

MongoDB is on **27018** and Qdrant on **6335**, not their conventional 27017 and 6333.
Both defaults are already answered on the development machine by services belonging to
other projects, and sharing a database server means sharing a failure — another project's
`docker compose down -v` would take this one's corpus with it. Each has its own container
and its own named volume.

---

## The two halves of the backend

The single most important boundary in the codebase:

```
learnmate/     the engine. Knows nothing about HTTP, users or requests.
               A library that ingests PDFs and generates from them.

app/           the web layer. Accounts, access control, endpoints, the job queue.
```

`learnmate/` is single-user and synchronous: give it a PDF and it will ingest it, give it a
question and it will answer. `app/` is what turns that into a service several students can
use at once. The rule the layering exists to enforce is that **a router never touches the
engine or the database directly, and a service never raises an HTTPException**.

```
integrated-backend/
├── server.py              FastAPI app: CORS, routers, /api/health
├── app/
│   ├── auth/              bcrypt hashing, JWT issue and verify
│   ├── routers/           endpoints — validate input, delegate, return
│   ├── services/          the work, called by routers and the job worker alike
│   ├── jobs/              the background queue (worker.py, runners.py)
│   ├── deps.py            get_current_user, the dependency every protected route uses
│   └── errors.py          engine exceptions → HTTP status codes, in one place
└── learnmate/
    ├── ingestion/         validate → extract → clean → chunk → embed
    ├── chat_agent/        a LangGraph state machine, one pass per message
    ├── resource_agent/    a LangGraph state machine, one pass per resource
    ├── evaluator/         two gates: structural validators, then an LLM judge
    ├── llm/               three interchangeable model backends
    └── storage/           MongoDB, GridFS and the vector store
```

---

## Everything slow is a job

Local inference on a 3B model takes tens of seconds to minutes. No browser holds a
connection that long and no proxy allows it, so every slow endpoint answers immediately
with a job id and the client polls:

```
POST /api/documents/upload          →  202 {document, job_id}
POST /api/resources/generate        →  202 {job_id}
POST /api/chat/sessions/{id}/messages →  202 {job_id}

GET  /api/jobs/{job_id}             →  queued | running | done | failed
                                       + progress, then result
```

A job record lives in MongoDB, not in memory, so a poll works regardless of which process
answers it and a client that reloads the page does not lose its place.

**One worker thread, and that is a correctness requirement rather than a resource one.**
`llama_cpp.Llama` holds a single mutable context: two threads generating at once interleave
their tokens and corrupt both replies. Locks sit next to the things they protect —
generation in `llm/llamacpp.py`, model loading in `llm/runtime.py`, `llm/embeddings.py` and
`llm/rerank.py` — so a job's database and network work no longer blocks anything.

### The chat turn has two milestones

Writing an answer is the fast half of a turn; judging it, and regenerating when the judge
says no, is the slow half. So the reply is handed over as soon as it exists rather than
when the turn ends:

```
tokens stream          →  progress.partial       the answer being typed
reply complete         →  progress.reply_ready   a finished answer, readable now
judge runs, may retry  →  (text frozen, off-screen)
job done               →  result                 the winning attempt
```

A regeneration is deliberately **not** streamed over the visible answer — replacing a
finished paragraph with a half-written one reads as the assistant having second thoughts in
public. If the retry scores better, the finished result swaps it in once, cleanly.

---

## Data model

Ten MongoDB collections plus one GridFS bucket, and one Qdrant collection.

| Collection | Holds |
|---|---|
| `users` | accounts: email, bcrypt hash, name |
| `user_documents` | who may see which document |
| `documents` | one row per **distinct file**, keyed by the SHA-256 of its bytes |
| `pages` | cleaned page text — what the models actually read |
| `chunks` | chunk records (vectors live in Qdrant) |
| `sessions` | which PDF a chat session is bound to |
| `chat_turns` | one row per turn, with mode, score, pages on the assistant's |
| `resources` | generated material with its verdict and attempt trail |
| `evaluations` | every verdict, passes included — the quality log |
| `jobs` | the background queue |
| `pdfs` (GridFS) | the original files |

Documents are keyed by content hash, so one PDF is stored and embedded **once** however
many people upload it. That is also why ownership cannot be a field on the document and
lives in `user_documents` instead.

---

## The frontend

React 19 with Vite, React Router and Tailwind. `src/api/` wraps every endpoint on one
axios instance with two interceptors: attach the token on the way out, and on a 401 clear
the session and redirect to `/login`.

```
src/
├── api/          one module per resource, over a shared axios client
├── context/      AuthProvider — token, user, and a startup /me verification
├── components/   Layout, Sidebar, Topbar, PublicLayout, chat and chart pieces
├── hooks/        useJob — run a 202 endpoint and poll it to completion
└── pages/        one per route
```

Routes fall into three kinds, and the middle one is the reason the router is not just a
list:

| Kind | Routes | Frame |
|---|---|---|
| open | `/login`, `/register` | none |
| explore | `/` (Home), `/about`, `/tour` | public header when signed out, app rail when signed in |
| protected | `/dashboard`, `/documents`, `/resources`, `/chat`, `/analytics`, `/account` | app rail, redirect to `/login` |

`/` is Home rather than a redirect to the dashboard: a first-time visitor landing on a login
form has been asked to commit before being told what to.

`useJob` is the hook the whole app is shaped around — it takes the function that produces
the 202, reads the job id off it, polls until the job finishes, and exposes `status`,
`progress` and finally `result` or `error`. It aborts on unmount, so navigating away
mid-generation stops the polling instead of setting state on a dead tree.

---

## Request path, end to end

One chat message, from click to answer:

```
1  Chat page          POST /api/chat/sessions/{id}/messages
2  router             checks ownership, enqueues, returns 202 {job_id}
3  worker thread      picks it up, marks the job running
4  service            builds a ChatAgent for this session and user
5  chat_agent graph   rewrite → retrieve → generate → evaluate → decide → persist
6  runner             streams tokens onto progress.partial as they arrive
7  frontend           useJob polls; StreamingMessage renders the text
8  worker             writes the result, marks the job done
9  frontend           swaps the streaming bubble for the stored turn
```

The graph in step 5 is one pass of a LangGraph state machine with a single conditional
edge — accept the reply, or regenerate it with the judge's instruction. It is described in
`README-MACHINE-LEARNING.md`.

---

## Access control

Every protected route depends on `get_current_user`, which verifies the JWT and loads the
account. Ownership is then checked **in the service layer**, on every path that names a
document, session or resource — `services/ownership.py` is the only place that decision is
made, so there is no route that forgot to ask.

Checks happen *before* work is queued, so posting into somebody else's session is a 403
immediately rather than a job that fails a minute later.

---

## Configuration

Two files, both read from `integrated-backend/.env`:

- `learnmate/config.py` — the engine: which models, which databases, which thresholds
- `app/config.py` — the web layer: JWT secret and expiry, CORS origin, password rules

`.env.example` documents every setting with the value the code uses when it is absent.
`JWT_SECRET_KEY` is the only one with no default, deliberately: a fallback secret works in
development, ships unnoticed, and makes every token it ever signed forgeable.

Swapping the generator for a different model — a finetune, a served endpoint, or a cloud
API — is two lines of `.env` and no code change.
