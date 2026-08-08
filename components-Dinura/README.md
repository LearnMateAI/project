# LearnMate

A study assistant that runs entirely on your own machine. You give it a PDF; it answers
questions about that PDF, and generates study material from it — multiple-choice
questions, short-answer practice questions, key points and summaries.

Nothing is sent to an external API. Three local models do the work:

| Model | Job | Size |
|---|---|---|
| Qwen2.5-3B-Instruct | writes chat replies and study resources | 2.0 GB |
| Llama-3.2-3B-Instruct | grades what the generator wrote | 1.9 GB |
| all-MiniLM-L6-v2 | turns text into vectors for retrieval | 90 MB |

The generator and the judge are **deliberately different model families**. A judge sharing
the generator's weights rates its own writing style highly, and the quality gate stops
firing.

---

## Quickstart

```bash
cd components-Dinura

# 1. dependencies
python -m venv venv
venv\Scripts\pip install -r requirements.txt

# 2. both databases, each in its own container with its own volume
docker compose up -d

# 3. check models, databases and settings before anything slow runs
venv\Scripts\python cli.py doctor

# 4. either entry point:
venv\Scripts\python cli.py ingest data\constitution.pdf --session s1   # one command at a time
python learnmate\full_program.py                                       # guided walkthrough
```

The two GGUF models download from Hugging Face on first use (~4 GB, once).

**Two ways in**, and they suit different jobs:

- **`cli.py`** — one verb per command, scriptable. This is the day-to-day interface, and
  the only one with the maintenance verbs: `stats`, `export`, `delete`, `docs`.
- **`learnmate/full_program.py`** — a guided menu that walks the whole workflow in one
  session, plus `--demo` as a one-command smoke test. It finds the project's virtualenv by
  itself, so plain `python` works without activating it.

`cli.py doctor` is the first thing to run whenever something misbehaves — it reports which
model files exist, whether each database is reachable, and what every threshold is set to.
`full_program.py` runs the same check on startup, so a stopped container is reported in one
line instead of surfacing minutes into an ingest.

**Expect it to be slow.** Everything runs on CPU: a chat turn is 20–60 seconds and a
graded resource 60–120 seconds. `--no-eval` skips the quality gate and roughly halves
that.

---

## The workflow

Everything starts with one PDF and one **session**.

```
                    ┌─────────────────────────────────────────┐
   your PDF ───────►│  INGESTION                              │
                    │  extract → clean → chunk → embed        │
                    └───────────┬─────────────────────────────┘
                                │
                 ┌──────────────┴───────────────┐
                 ▼                              ▼
        ┌─────────────────┐            ┌─────────────────┐
        │ MongoDB :27018  │            │ Qdrant :6335    │
        │ the PDF itself  │            │ chunk vectors   │
        │ page text       │            └────────┬────────┘
        │ sessions        │                     │
        │ chat history    │                     │
        │ resources       │                     │
        └────────┬────────┘                     │
                 │                              │
      ┌──────────┴──────────┐                   │
      ▼                     ▼                   │
┌───────────────┐   ┌─────────────────┐         │
│ CHAT AGENT    │◄──┤ retrieval       │◄────────┘
│ ask a question│   └─────────────────┘
└───────┬───────┘
        │            ┌─────────────────┐
        ▼            │ RESOURCE AGENT  │
   ┌─────────┐       │ mcq / summary / │
   │EVALUATOR│◄──────┤ keypoints /     │
   │ grades  │       │ practice_qsn    │
   │ + retry │       └─────────────────┘
   └─────────┘
```

### Step 1 — Ingest a PDF

You give a file path. The system then:

1. **Validates** it — not empty, not over 10 MB, and this session doesn't already hold a
   different PDF. All three checks happen **before** anything is written, because
   embedding is the expensive part and a rejected upload must not cost you the PDF you
   already had working.
2. **Stores the file whole** in MongoDB (GridFS), identified by the SHA-256 of its bytes.
   Upload the same PDF twice under different names and it is recognised as one document —
   no re-embedding.
3. **Extracts and cleans** each page: removes running heads and footers (any short line
   appearing on more than half the pages), deletes standalone page numbers, rejoins words
   hyphenated across a line break, and flattens line breaks — because a line break in a
   PDF reflects the column, not the sentence.
4. **Splits** the cleaned pages into ~900-character overlapping chunks.
5. **Embeds** the chunks and stores the vectors in Qdrant.
6. **Stores the whole page text too**, separately from the chunks.
7. **Binds the session** to the document — but only now, once the document has proved
   usable.

### Step 2a — Chat

One question is one pass through a five-node state machine:

```
rewrite ──► retrieve ──► generate ──► evaluate ──► decide ─┬─► persist ─► END
                            ▲                              │
                            └────────── regenerate ────────┘
```

- **rewrite** turns a follow-up into a standalone question. *"What about its national
  flag?"* becomes *"What is the national flag of the Republic of Sri Lanka?"*. This runs
  **before** retrieval — searching on the pronoun would already have failed.
- **retrieve** searches the vectors and **decides the mode from the score**, not by asking
  the model. Top score ≥ 0.25 → **PDF mode** (answer strictly from the retrieved chunks).
  Below → **general mode** (answer from the model's own knowledge).
- **generate** writes the reply using whichever system prompt the mode calls for.
- **evaluate** hands it to the judge. In PDF mode the judge is given the chunks and
  anything beyond them counts as a hallucination; in general mode it can only grade
  relevance, coherence and informativeness.
- **decide** accepts, or sends it back once with the judge's fix instruction.
- **persist** saves the turn, so the next question has history to resolve against.

### Step 2b — Generate study resources

```
generate ──► check ──► decide ─┬─► persist ─► END
    ▲                          │
    └───────── regenerate ─────┘
```

First the system picks **which part of the PDF to use**. A whole book doesn't fit in a 4k
context window, so:

- give it a **topic** → the pages whose text best matches it
- give it **page numbers** → exactly those pages
- give it **neither** → the opening of the document

The unit is always a **whole page**, never the retrieved chunks. Chunks overlap by ~150
characters, so joining them repeats text at every boundary and starts mid-sentence — a
generator handed that writes questions about the fragments.

Then `check` runs **two gates, cheapest first**:

1. **Structural validators** — plain Python, microseconds. Four options per question? Is
   the correct answer actually one of them? Duplicate options? Is the answer always in
   slot B, or always the longest? An empty summary?
2. **The LLM judge** — ~25 seconds, and only ever spent on content that is already
   well-formed.

If either rejects, the fix instruction goes back into the next prompt along with the
rejected attempt, so the model *revises* rather than starting over.

---

## What's in `components-Dinura/`

| Path | What it is |
|---|---|
| `learnmate/` | the library — all the logic lives here |
| `cli.py` | command line: `ingest`, `chat`, `generate`, `docs`, `resources`, `stats`, `export`, `delete`, `doctor` |
| `learnmate/full_program.py` | guided end-to-end walkthrough, and `--demo` as a smoke test |
| `docker-compose.yml` | both databases, each with a named volume |
| `requirements.txt` | pinned dependencies, with notes on which pins actually matter |
| `.env.example` | every setting, with its default; copy to `.env` |
| `models/` | the two GGUF files (gitignored, downloaded on first use) |
| `data/` | sample PDFs |

---

## What's in `learnmate/`

Six packages. Each one is decomposed into small single-purpose files, and every file
opens with a docstring saying what it does and why it is that way.

```
learnmate/
├── config.py          every tunable setting, all overridable by environment variable
├── full_program.py    the guided end-to-end program
├── ingestion/         PDF → cleaned pages → chunks → vectors → a bound session
├── storage/           MongoDB and the vector database
├── llm/               access to the three models
├── chat_agent/        the question-answering state machine
├── resource_agent/    the study-material generator
└── evaluator/         the two quality gates
```

### `ingestion/` — getting a PDF into the system

| File | Does |
|---|---|
| `clean.py` | extracts pages with PyMuPDF; strips running heads, page numbers, hyphenation |
| `chunking.py` | splits cleaned pages into the overlapping chunks that get embedded |
| `sessions.py` | session kinds, one-PDF-per-session, and the binding |
| `pipeline.py` | `ingest_pdf()` — the order all of the above happens in |
| `source_text.py` | `build_source_text()` — what a resource session reads back |

**The distinction that matters:** `chunking.py` produces text sized for *retrieval*;
`source_text.py` reads back whole pages for *reading*. They are not interchangeable.

**Sessions.** An upload always belongs to a session, and a session is opened for one
purpose:

```bash
python cli.py ingest constitution.pdf --session s1                  # --for chat (default)
python cli.py ingest constitution.pdf --session s2 --for resource
python cli.py ingest constitution.pdf --session s3 --for both
```

```python
from learnmate import ingest_pdf

ingest_pdf("constitution.pdf", session_id="s1")                          # chat (default)
ingest_pdf("constitution.pdf", session_id="s2", session_for="resource")  # generation
ingest_pdf("constitution.pdf", session_id="s3", session_for="both")      # both
```

Both purposes need identical ingestion, so the kind is a statement of intent, not an
optimisation. Using a session for the other purpose is refused, with the call that fixes
it — and following that advice is nearly free, because an already-ingested PDF is not
re-embedded. (`full_program.py` always opens sessions `for="both"`, so you will not hit
this unless you use `cli.py` or the library directly.)

### `storage/` — two databases

```
MongoDB (:27018)   the PDFs, page text, sessions, chat history, resources, evaluations
Qdrant  (:6335)    the chunk vectors
```

**The split is deliberate and asymmetric.** Nothing in MongoDB can be derived from
anything else, so losing it loses the corpus. The vectors are computed *from* that page
text, so losing Qdrant only costs a re-ingest. That is why the vector backend is swappable
and MongoDB is not.

| File | Does |
|---|---|
| `mongo.py` | the connection, `StorageUnavailable` |
| `indexes.py` | every index — including three that enforce rules, not speed |
| `ids.py` | ObjectId coercion, shared by everything that queries by id |
| `pdf_files.py` | the PDF bytes, in GridFS |
| `documents.py` | the document record: store, look up, resolve, delete |
| `pages.py` | cleaned page text |
| `pdf_store.py` | one facade over those three |
| `sessions.py` | which PDF a session is about, and what for |
| `history.py` | chat turns |
| `resources.py` | generated resources, with their whole attempt trail |
| `evaluations.py` | the verdict log and its statistics |
| `content_store.py` | one facade over those four |
| `vectors.py` | picks the vector backend |
| `qdrant_vectors.py` | Qdrant: real HNSW index, filtering server-side |
| `mongo_vectors.py` | the same interface over MongoDB, when you don't want a second service |

Three indexes are `unique` because they enforce a rule structurally: one document per set
of bytes, re-ingesting overwrites a chunk in place, and one PDF per session.

Both databases run in containers with **named volumes**, so `docker compose down` keeps
your data and only `docker compose down -v` clears it.

### `llm/` — reaching the three models

| File | Does |
|---|---|
| `registry.py` | `get_generator_llm()` and `get_judge_llm()` — the entry points |
| `llamacpp.py` | backend 1: a local GGUF, in-process, with JSON grammars |
| `http_api.py` | backend 2: a served OpenAI-compatible endpoint |
| `messages.py` | LangChain messages ↔ the role/content dicts both backends want |
| `runtime.py` | the GGUF weight cache, released cleanly at exit |
| `download.py` | fetches a missing GGUF from Hugging Face |
| `json_output.py` | recovers JSON from an unconstrained reply |
| `embeddings.py` | MiniLM behind LangChain's `Embeddings` interface |

**There is no Qwen class and no Llama class.** Both chat models share every line of code;
which family loads is the GGUF path in config. Swapping in a finetuned model is two lines
of `.env`.

**Why these are custom classes** rather than a stock integration: the `response_schema`
argument. A 3B model politely asked for JSON returns prose about half the time. llama.cpp
can instead compile a JSON schema into a *decoding grammar*, making malformed output
impossible. Every structured thing in this project depends on it.

Caching happens at three separate layers — wrapper objects by role and temperature, actual
weights by file, and the embedding model. Two wrappers can share one set of weights.

### `chat_agent/` — answering a question

| File | Does |
|---|---|
| `state.py` | `ChatState` — what flows between nodes |
| `rewrite.py` | node 1 — resolve the follow-up into a standalone question |
| `retrieve.py` | node 2 — search the vectors, pick PDF or general mode |
| `generate.py` | node 3 — write the reply |
| `evaluate.py` | node 4 — judge it |
| `routing.py` | the accept-or-retry branch |
| `persist.py` | node 5 — save the turn |
| `prompts.py` | the three system prompts |
| `graph.py` | the LangGraph wiring |
| `agent.py` | `ChatAgent` — the public entry point |

```python
from learnmate import ChatAgent

agent = ChatAgent(session_id="s1", doc_id=doc_id)
result = agent.ask("What are the directors' duties?")
print(result["reply"], result["accepted"], result["mode"])
```

The retry budget is one regeneration, and the regenerated reply is returned **whether or
not it passes** — a student mid-conversation needs an answer, and `accepted` says whether
it was reviewed clean.

### `resource_agent/` — generating study material

Four resource types, **one file each**:

| File | Produces |
|---|---|
| `mcq.py` | `{question, options[4], correct_answer}` |
| `practice_qsn.py` | `{question, answer}` |
| `keypoints.py` | `["point", ...]` |
| `summary.py` | one block of connected prose |

Each owns its prompt, JSON schema, how to read the reply and how to render it. Everything
else is shared, so a fifth type is one new file plus one line in `tasks.py`.

| File | Does |
|---|---|
| `task.py` | the contract every resource type implements |
| `tasks.py` | the registry |
| `state.py` | `ResourceState` |
| `generate.py` | node 1 — ask the generator, folding in a critique on retry |
| `check.py` | node 2 — both gates |
| `routing.py` | the accept-or-retry branch |
| `persist.py` | node 3 — store the resource and its attempt trail |
| `graph.py` | the wiring |
| `agent.py` | `generate_resource()` — the public entry point |

### `evaluator/` — the two gates

```
gate 1   structural validators   plain Python, microseconds
gate 2   an LLM rubric grade     ~25 seconds
```

| File | Gate | Does |
|---|---|---|
| `normalise.py` | 1 | comparison-safe text |
| `mcq_rules.py` | 1 | per-question faults **and** set-wide biases |
| `text_rules.py` | 1 | summary, keypoints, practice questions |
| `validators.py` | 1 | the dispatcher |
| `rubrics.py` | 2 | the grading criteria, one per task |
| `prompt.py` | 2 | system prompt and message assembly |
| `verdict.py` | 2 | the schema, parsing, and fail-closed verdicts |
| `judge.py` | 2 | orchestration |

The set-wide MCQ rules are the interesting ones: every question can be individually
perfect while the set as a whole is guessable — the answer always in the same slot, or
always the longest option. No single-question check can see that.

**Everything fails closed.** A judge that cannot be parsed or reached returns a *failing*
verdict, not an exception — the caller is mid-loop and needs a decision, and silently
passing unreviewed content through is the one outcome worth ruling out.

A chat reply has no structural gate: free prose has nothing mechanical to check, so it
goes straight to gate 2.

---

## Running it

### `cli.py` — one command at a time

```
python cli.py doctor                                    check models, databases, settings
python cli.py ingest <pdf> [--session ID] [--force]     store + index one PDF
              [--for chat|resource|both]                 what the session is for
python cli.py docs [--limit N]                          list ingested documents
python cli.py chat [--session ID] [--doc X]             interactive chat
              [--threshold N] [--no-eval] [--quiet]
python cli.py generate <task> [--session ID] [--doc X]  generate a resource
              [--count N] [--topic "..."] [--pages 3-7]
              [--max-source-chars N] [--threshold N] [--no-eval] [--json] [--quiet]
python cli.py resources [--doc X] [--task T]            list what has been generated
              [--accepted] [--show] [--limit N]
python cli.py stats                                     score distribution per task
python cli.py export <doc> <destination>                write a stored PDF back to disk
python cli.py delete <doc>                              remove a document and its chunks
```

`<task>` is one of `mcq`, `practice_qsn`, `keypoints`, `summary`.

`--doc` accepts an id, an exact filename, or a unique fragment (`--doc constitution`). A
fragment matching several documents is rejected rather than guessed at. Omit it and the
session's own PDF is used; omit both and it falls back to the most recently ingested one.

`stats`, `export`, `delete` and `docs` exist only here — they are maintenance verbs that
do not belong in a guided walkthrough.

### `full_program.py` — the whole workflow in one session

```
python learnmate\full_program.py                       interactive menu
python learnmate\full_program.py --demo                run everything without prompting
python learnmate\full_program.py --demo --no-eval      same, roughly half the time
python learnmate\full_program.py --pdf notes.pdf --ask "..."
python learnmate\full_program.py --topic "fundamental rights"
```

The menu:

| | |
|---|---|
| 1 | Upload a PDF (by file path) |
| 2 | Chat about it |
| 3–6 | Generate MCQs / summary / key points / practice questions individually |
| 7 | Generate all four |
| 8 | Show stored state — documents, session, resources, vector counts |
| 9 | Set a topic for generation |
| e | Toggle evaluation (the judge and its retry) |
| 0 | Quit |

### Using it as a library

This is the interface the backend will integrate against.

```python
from learnmate import ChatAgent, build_source_text, generate_resource, ingest_pdf

report = ingest_pdf("notes.pdf", session_id="s1", session_for="both")
doc_id = report["doc_id"]

agent = ChatAgent(session_id="s1", doc_id=doc_id)
reply = agent.ask("What are the directors' duties?")
# {reply, mode, accepted, verdict, contexts, scores, attempts, ...}

source = build_source_text(doc_id, topic="directors' duties")
result = generate_resource("mcq", source, count=5, doc_id=doc_id)
# {task, content, accepted, verdict, attempts, resource_id}
```

### Reading the evaluation log

```bash
python cli.py stats
```

```python
from learnmate.storage import content_store

content_store.evaluation_stats()   # score distribution per task
content_store.stage_counts()       # which gate decided each attempt
```

The `distinct` column is the important one. A judge whose scores cluster in a narrow band
cannot separate good from bad at **any** threshold — that is a rubric problem, not a
threshold problem. The stage counts show which gate decided each attempt: if the validator
is deciding most of them, the generation prompt needs work.

---

## Configuration

Everything lives in `config.py` and is overridable by environment variable. Copy
`.env.example` to `.env` and edit. The settings you are most likely to touch:

| Variable | Default | Meaning |
|---|---|---|
| `LEARNMATE_GENERATOR_MODEL` | `models/qwen2.5-3b-…gguf` | swap in your finetuned model |
| `LEARNMATE_GENERATOR_BACKEND` | `llamacpp` | or `http` for a served model |
| `LEARNMATE_MONGODB_URI` | `mongodb://localhost:27018` | the container from `docker-compose.yml` |
| `LEARNMATE_VECTOR_BACKEND` | `qdrant` | or `mongodb`, to avoid a second service |
| `LEARNMATE_RELEVANCE_THRESHOLD` | `0.25` | below this, chat answers from general knowledge |
| `LEARNMATE_EVALUATOR_THRESHOLD` | `70` | judge score needed to accept |
| `LEARNMATE_MAX_ATTEMPTS` | `2` | one generation plus one retry |
| `LEARNMATE_MAX_PDF_MB` | `10` | upload limit |
| `LEARNMATE_ONE_PDF_PER_SESSION` | `1` | set `0` to lift the restriction |

### Why the ports are unusual

Both services publish on non-default host ports — MongoDB on **27018**, Qdrant on
**6335** — because this machine already runs another project's MongoDB on 27017 and
another Qdrant on 6333. Sharing a server means sharing a failure: another project's
`docker compose down -v` would take LearnMate's PDFs and generated resources with it.

---

## Design decisions worth knowing

**The mode is decided by a number, not by the model.** Whether chat answers from the PDF
or from general knowledge comes from the retrieval score. A number can be tuned and
logged; a second LLM call can be wrong and costs 25 seconds.

**Rewrite runs before retrieval.** *"What about his powers?"* embeds to nothing useful.
Resolved first, it retrieves correctly.

**Chunks for retrieval, whole pages for reading.** Two different products of one ingest,
not interchangeable.

**The cheap gate runs first.** Most bad generations fail mechanically. Catching those in
microseconds means the 25-second judge is only spent on well-formed content.

**Failed output is still returned, and still stored.** Marked `accepted: False`. Hiding it
would make the failure rate invisible.

**The whole attempt trail is kept**, not just the winner. Whether the threshold is set
anywhere near right is unanswerable after the fact if you only keep what passed.

**The retry budget is 2 on purpose.** A 3B judge tends to oscillate rather than converge
over more rounds; the third attempt is usually a worse version of the first.

---

## Troubleshooting

| Symptom | Cause and fix |
|---|---|
| `No module named 'bson'` / `'langchain_text_splitters'` | You used the system Python. Use `venv\Scripts\python`, or run `full_program.py`, which switches by itself. |
| `Cannot reach MongoDB at …` | `docker compose up -d mongo` |
| `Cannot reach the Qdrant server at …` | `docker compose up -d qdrant` |
| Qdrant container crash-loops after an image bump | Its on-disk format isn't backward compatible. `docker compose down -v` and re-ingest — nothing is lost, the vectors are derived from MongoDB. |
| `Session 'x' is already about y.pdf` | One PDF per session. Use a new session id. |
| `Session 'x' was opened for chat, not resource generation` | Open a session with `--for resource`; the PDF is not re-embedded. |
| `No extractable text in …` | A scanned PDF. It needs OCR before it can be indexed. |
| Everything is very slow | Expected on CPU. Use `--no-eval` to skip the judge, or set `LEARNMATE_N_GPU_LAYERS` to offload to a GPU. |

---

## Known limitations

- **Key-point grading is weak.** The `keypoints` rubric scores faithful content around 40
  against a threshold of 70 — the 3B judge produces one complaint per rubric criterion
  regardless of the content. The other three resource types separate good from bad by
  50–79 points. Softening the rubric's "missing the central point is a serious fault"
  clause is the place to start.
- **Generation quality depends heavily on which passage is used.** With no `--topic`, the
  source is the opening of the document, which for a book-style PDF is the title page and
  preamble. Pass a topic for anything substantive.
- **Scanned PDFs are not supported** — there is no OCR step.
- **One PDF per session by design.** Combining several documents into one corpus and
  chatting across all of them is not supported.
