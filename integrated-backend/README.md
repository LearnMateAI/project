# LearnMate — integrated backend

Upload a PDF; ask it questions, and generate study material from it — multiple-choice
questions, short-answer practice questions, key points and summaries. Everything is graded
by a second model before you see it.

This folder is the merge of the two backends that grew separately:

| From | What it contributed |
|---|---|
| `components-Dinura/` | the whole AI engine — ingestion, retrieval, both LangGraph agents, the evaluator, all persistence |
| `backend/` | the web layer — JWT auth, bcrypt, the REST shapes the React frontend calls, PDF upload validation |

Neither original folder is modified, and neither is imported from. `integrated-backend/`
runs on its own.

---

## Quickstart

```bash
cd integrated-backend

# 1. both databases, each in its own container with its own volume
docker compose up -d

# 2. dependencies
python -m venv venv
venv\Scripts\pip install -r requirements.txt

# 3. settings -- JWT_SECRET_KEY is the only one with no default
copy .env.example .env
python -c "import secrets; print(secrets.token_hex(32))"     # paste into JWT_SECRET_KEY

# 4. models (~4 GB, once). Skip this: they download on first use.
#    They are already in models/ on the development machine.

# 5. run -- 8010, not 8000: an unrelated simplytask-backend container answers 8000,
#    and uvicorn binds it without complaining, so every route appears to 404.
venv\Scripts\python -m uvicorn server:app --reload --port 8010
```

Then open <http://localhost:8010/api/health>. It should say `ok`, with both databases
reachable. Interactive API docs are at <http://localhost:8010/docs>.

To check the whole thing end to end:

```bash
venv\Scripts\python scripts\smoke_test.py data\Company-law-part1-notes.pdf --base-url http://127.0.0.1:8010
```

That registers a throwaway account, uploads, ingests, generates, chats and reads the
analytics back, printing a pass/fail line per step. On the local models it takes several
minutes; `--fast` skips the judge and roughly halves it.

---

## How it is put together

```
integrated-backend/
├── server.py         the FastAPI app: CORS, routers, /api/health
├── app/              the web layer
│   ├── auth/         accounts: bcrypt, JWT, registration and login rules
│   ├── routers/      the endpoints
│   ├── services/     the work -- called by routers and by the job worker alike
│   └── jobs/         the background queue
└── learnmate/        the engine
    ├── ingestion/    validate -> extract -> clean -> chunk -> embed
    ├── chat_agent/   a LangGraph state machine, one pass per message
    ├── resource_agent/  a LangGraph state machine, one pass per resource
    ├── evaluator/    two gates: structural validators, then an LLM judge
    ├── llm/          three interchangeable model backends
    └── storage/      MongoDB, GridFS and the vector store
```

The boundary is worth knowing before changing anything: **`learnmate/` knows nothing about
HTTP or users.** It is a library that ingests PDFs and generates from them. Everything
about accounts, access control and request handling is in `app/`. A router never touches
the database directly and a service never raises an HTTPException — that is what lets the
same service function serve a request and a background job.

Each package has a docstring explaining what is in it and in what order to read it. Start
with `learnmate/__init__.py`.

### Three models, and why the judge is a different one

| Model | Job | Size |
|---|---|---|
| Qwen2.5-3B-Instruct | writes chat replies and study resources | 2.0 GB |
| Llama-3.2-3B-Instruct | grades what the generator wrote | 1.9 GB |
| all-MiniLM-L6-v2 | turns text into vectors for retrieval | 90 MB |

The generator and the judge are deliberately different model families. A judge sharing the
generator's weights rates its own writing style highly, and the quality gate stops firing —
which looks like everything passing rather than like a broken evaluator.

#### Running the domain finetune instead of the stock generator

The ML track (`model-Thevindu/`) trains a QLoRA adapter on Qwen2.5-1.5B-Instruct over the
`lm-legal-v0.1` Sri Lankan legal corpus. It ships as a ~74 MB adapter, which this backend
cannot load — llama.cpp runs GGUF — so one script bridges the two:

```bash
pip install "peft>=0.20" "gguf>=0.10" sentencepiece   # build-time only
python scripts/build_finetuned_gguf.py    # merge adapter into base, then convert
```

The first run also downloads the ~3.1 GB base weights the adapter was trained
against, which dominates the wall clock on a slow link; the merge and conversion
themselves are a few minutes. Every step is skipped if its output already exists, so
an interrupted build resumes rather than restarting.

That writes `models/learnmate-legal-qwen2.5-1.5b-q8_0.gguf` plus a `.json` sidecar
recording which training run it came from. Point the generator at it in `.env` — and empty
both download settings with it, because a locally built file exists in no repository and
the base model's repo/file would otherwise quietly download the stock 3B and run *that*
under the finetune's name:

```
LEARNMATE_GENERATOR_MODEL=models/learnmate-legal-qwen2.5-1.5b-q8_0.gguf
LEARNMATE_GENERATOR_REPO=
LEARNMATE_GENERATOR_FILE=
```

Know what the swap costs before making it. The finetune is 1.5B where the stock generator
is 3B, so it is a weaker general-purpose writer, and it did **not** pass the ML track's
acceptance gate — 0.557 / 0.621 LLM-judge accuracy against a 0.70 minimum, losing to the
API fallback on both accuracy and groundedness
(`model-Thevindu/03_testing_and_versioning/version_registry.csv`). It is better on
statutory question answering and weaker elsewhere: a deliberate demo choice, not a
promotion. The rollback is the three lines above set back to their defaults.

### Two databases

`docker compose up -d` starts both.

- **MongoDB (`:27018`)** — the PDFs in GridFS, their cleaned page text, accounts, session
  bindings, chat history, generated resources, the evaluation log and the job queue.
- **Qdrant (`:6335`)** — the chunk embeddings.

The split is asymmetric on purpose: nothing in MongoDB can be derived from anything else,
so losing it loses the corpus; the vectors are computed from that page text, so losing
Qdrant only costs a re-ingest. That is why the vector backend is swappable
(`LEARNMATE_VECTOR_BACKEND=mongodb` keeps everything in one service) and MongoDB is not.

Both use non-default ports, because `27017` and `6333` on this machine are answered by
other projects' services and sharing a server means sharing a failure.

---

## The two design decisions worth knowing

### 1. One PDF is stored once, however many people upload it

A document is identified by the SHA-256 of its bytes, with a unique index on it. Embedding
is the expensive step — a few thousand chunks through a CPU model — so five students
uploading the same lecture notes pay it once.

Which means ownership cannot be a field on the document. It lives in its own collection:

```
documents        what this PDF is        one row per set of bytes    (shared)
user_documents   whose library it is in  one row per person per doc  (private)
```

Every access check asks `user_documents`. Deleting removes your library entry; the bytes,
pages, chunks and vectors go only when the last owner deletes it.

### 2. Slow work runs on a queue, not in the request

A chat turn is 30–60 seconds on the local models. A forty-question set across a whole book
is several minutes. No browser holds a connection that long and no proxy allows it, so:

```
POST /api/documents/upload   -> 202 {job_id}
POST /api/resources/generate -> 202 {job_id}
POST /api/chat/.../messages  -> 202 {job_id}

GET  /api/jobs/{job_id}      -> queued | running | done | failed  + progress + result
```

Poll every second or two. The finished job's `result` is exactly what a synchronous
endpoint would have returned.

There is **one** worker thread, and that is a correctness requirement rather than a
resource one: `llama_cpp.Llama` holds a single mutable context, so two threads generating
at once interleave their tokens and corrupt both replies. See `app/jobs/worker.py`.

---

## API

Everything except `register` and `login` needs `Authorization: Bearer <token>`.

### Auth

| | |
|---|---|
| `POST /api/auth/register` | `{name, email, password}` → `{token, user}` |
| `POST /api/auth/login` | `{email, password}` → `{token, user}` |
| `GET /api/auth/me` | who this token belongs to |

### Documents

| | |
|---|---|
| `POST /api/documents/upload` | multipart `file`, `subject` → **202** `{document, job_id}` |
| `GET /api/documents` | your library |
| `GET /api/documents/{id}` | one document, with `processing_status` |
| `GET /api/documents/{id}/file` | the PDF itself |
| `GET /api/documents/{id}/pages?first=&last=` | the cleaned text the models actually read |
| `DELETE /api/documents/{id}` | remove from your library; purges if you were the last owner |

`processing_status` goes `Uploaded → Processing → Ready`, or `Failed Processing` with
`processing_error`. Nothing can be generated or chatted with until it is `Ready`.

### Resources

`POST /api/resources/generate` → **202** `{job_id}`

```jsonc
{
  "document_id": "…",
  "resource_type": "mcq | practice_qsn | keypoints | summary",
  "scope": "passage | document",
  "topic": "directors' duties",   // passage scope: picks the most relevant pages
  "pages": [12, 13, 14],          // passage scope: or name them exactly
  "count": 20,                    // items in total (or, for a summary, sentences)
  "per_page": 2,                  // document scope: a rate instead of a total
  "evaluate": true                // false skips the judge -- faster, unreviewed
}
```

**`scope` is the choice that matters, and it is not a speed knob.**

- `passage` — one continuous extract that fits the context window. This is *"five questions
  about directors' duties"*. Seconds to a minute.
- `document` — the whole PDF, split into groups of pages, each asked for its share, results
  pooled and de-duplicated. This is *"forty questions about this book"*. Minutes. A summary
  folds instead of pooling: every page is summarised, then the notes are folded in rounds
  until they fit one prompt.

Asking for forty questions at `passage` scope does not fail — it silently gives you forty
questions about the opening six thousand characters.

| | |
|---|---|
| `GET /api/resources?document_id=&resource_type=` | your resources, newest first |
| `GET /api/resources/{id}` | one, with its whole attempt trail |
| `DELETE /api/resources/{id}` | |

`summary` and `key_points` are still accepted as type names, so the current frontend keeps
working.

### Chat

| | |
|---|---|
| `POST /api/chat/sessions` | `{document_id, title?}` → a session |
| `GET /api/chat/sessions` | your conversations |
| `GET /api/chat/sessions/{sid}/messages` | the transcript |
| `POST /api/chat/sessions/{sid}/messages` | `{message}` → **202** `{job_id}` |
| `DELETE /api/chat/sessions/{sid}` | |

The finished job's `result`:

```jsonc
{
  "reply": "…",
  "standalone_query": "What are the President's powers?",  // the follow-up, resolved
  "mode": "pdf",          // or "general" -- see below
  "top_score": 0.61,
  "score": 84, "accepted": true,
  "contexts": [{ "page_number": 41, "text": "…", "score": 0.61 }]
}
```

`mode` is decided by the retrieval score, not by asking the model. `pdf` means the answer
was written from the chunks in `contexts` and judged strictly against them — anything they
do not support is a hallucination. `general` means nothing relevant was retrieved and the
model answered from its own knowledge. **A student needs to know which of those they are
reading**, so show it.

### Jobs and analytics

| | |
|---|---|
| `GET /api/jobs/{id}` | `{status, progress, result, error}` |
| `GET /api/jobs?status=&kind=` | your recent jobs |
| `GET /api/analytics` | activity counts and the evaluation score distribution |
| `GET /api/health` | both databases, both models, and what is configured |

---

## Switching to Gemini

The local models are private and free but slow. To trade that for speed, in `.env`:

```bash
LEARNMATE_GENERATOR_BACKEND=gemini
LEARNMATE_GENERATOR_MODEL=gemini-2.0-flash
LEARNMATE_JUDGE_BACKEND=gemini
LEARNMATE_JUDGE_MODEL=gemini-2.0-flash-lite
GEMINI_API_KEY=…
```

Nothing else changes — the agents, both graphs, the evaluator and the retry loop never
learn which backend answered. Keep the two roles on different models for the reason above.

A single role can be switched: running the generator on Gemini and the judge locally is a
reasonable middle ground, since the judge's ~25 seconds is the smaller half of the cost.

---

## Troubleshooting

**`/api/health` says `degraded`.** Read `checks`. `docker compose up -d`, then
`docker compose ps` to confirm both containers are healthy.

**Everything is slow.** Expected on `llamacpp`. The first request of a fresh process also
loads ~4 GB of weights. Watch `GET /api/jobs/{id}` — `progress.message` says what it is
doing. `evaluate: false` roughly halves generation time.

**A resource came back with fewer items than I asked for.** The shortfall is reported in
`generated` vs `requested`, never padded. The document was too short to support them, or
the generator repeated itself and the duplicates were dropped.

**Ingestion failed with "no extractable text".** A scanned PDF with no text layer. It needs
OCR before this can index it.

**Qdrant crash-loops after a version change.** Its on-disk segment format is not backward
compatible. `docker compose down -v` and re-ingest — nothing is lost, since the vectors are
derived from the page text in MongoDB.

**A job says "Interrupted by a server restart".** It was running when the process stopped;
the queue and the work both lived in that process's memory and cannot be resumed. Send it
again.

**Jobs fail as soon as I start a second server.** Run **one** server process against a
given MongoDB. The queue is in-process, so a second server marks the first's in-flight
jobs as interrupted on the way up. Running several would mean moving the queue out of
process memory — a real broker, or a Mongo-backed claim with a lease.

---

## Notes for the frontend

Three changes from what `frontend/api/routes.jsx` does today:

1. **Upload and generate now return `202 {job_id}`.** Both need a poll loop against
   `GET /api/jobs/{job_id}` rather than awaiting the response.
2. **`verification_status` is gone**, replaced by real evaluator output: `accepted`,
   `score`, `threshold`, `n_attempts`.
3. **`resource_type` gains `mcq`, `practice_qsn` and `keypoints`** — the three buttons
   currently disabled as "Coming Day 10" — plus the `scope` field.

Chat and analytics are new surfaces; `chat-home.jsx` and `user-analytics.jsx` are
placeholders today.
