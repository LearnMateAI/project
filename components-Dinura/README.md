# LearnMate — components-Dinura

A local study assistant over uploaded PDFs. Three agents share one MongoDB corpus:

| Agent | What it does |
| --- | --- |
| **chat_agent** | Answers questions about an ingested PDF, falling back to general knowledge when nothing relevant is retrieved |
| **resource_agent** | Generates MCQs, short-answer practice questions, key points and summaries from a document |
| **evaluator** | Grades what the other two produce and drives exactly one retry |

Both agents are [LangGraph](https://langchain-ai.github.io/langgraph/) state machines built
from LangChain components. Nothing is kept in a local cache directory: chunk vectors live
in a **Qdrant server**, and the PDFs, page text, generated resources, evaluation verdicts
and chat history live in **MongoDB**. Both are ordinary network services, so more than one
process can use the corpus at once.

---

## Quick start

```bash
# 1. dependencies
venv/Scripts/python -m pip install -r requirements.txt

# 2. start the vector database (MongoDB is expected to be running already)
docker compose up -d qdrant

# 3. check models, both databases and settings before anything slow runs
python cli.py doctor

# 3. upload one PDF (max 10 MB) for a chat session, and chat about it
python cli.py ingest data/raw_pdfs/constitution.pdf --session s1
python cli.py chat --session s1

# 4. upload the same PDF for a resource-generation session (nothing is re-embedded)
python cli.py ingest data/raw_pdfs/constitution.pdf --session s2 --for resource
python cli.py generate mcq --session s2 --count 5 --topic "fundamental rights"
python cli.py stats
```

`cli.py doctor` is the first thing to run when something misbehaves. It reports whether
each model file exists, whether MongoDB is reachable, which vector-search path is active,
and what every threshold is currently set to.

---

## How a turn works

### Chat

```
rewrite ─→ retrieve ─→ generate ─→ evaluate ─→ decide ─┬─→ persist ─→ END
                          ↑                            │
                          └────────── regenerate ──────┘
```

**`rewrite` runs before retrieval, not after.** A follow-up like *"what about his powers?"*
embeds to nothing useful; resolved against the history into *"what are the President's
powers?"* it retrieves correctly. Doing it in the other order retrieves on the pronoun.

**Mode is decided by retrieval, not by asking the model.** If the top chunk scores at or
above `RELEVANCE_THRESHOLD` the reply is written from those chunks and judged strictly
against them — anything they do not support is a hallucination. Otherwise the reply comes
from the model's own knowledge and is judged only on relevance, coherence and
informativeness. Holding a general-knowledge answer to a "cite your sources" rubric would
fail every time for no reason, so which rubric applies is decided by what was actually
retrieved.

The regenerated reply is returned **whether or not it clears the threshold** — a user
mid-conversation needs an answer — and `accepted` reports whether it was reviewed clean.

### Resource generation

```
generate ─→ check ─→ decide ─┬─→ persist ─→ END
    ↑                        │
    └──── regenerate ────────┘
```

`check` runs two gates, cheapest first:

1. **Structural validators** (plain Python, microseconds) — four options, `correct_answer`
   present among them, no duplicates, no *"all of the above"*, no position or length bias
   across the set, non-empty summary.
2. **LLM judge** (~25 s) — answerability, correctness, distractor quality, coverage.

Most bad generations fail mechanically, so the judge is only ever spent on content that is
already well-formed. The whole attempt trail is stored, not just the winner: a resource
that needed a retry, and what the judge objected to the first time, is the data that says
whether the threshold is set anywhere near right.

**The retry budget is one regeneration.** Raising it is not just slower — a 3B judge tends
to oscillate rather than converge, and the third attempt is usually a worse first attempt.

---

## Storage

Two services, split by what they are good at. Both are reachable over the network, so any
process that can reach them sees the same corpus.

### Qdrant — the vectors

A **server**, started with `docker compose up -d qdrant`, never the embedded mode.
`QdrantClient(path=...)` runs Qdrant inside the calling process and takes an exclusive
lock on a local directory, which means one process at a time and nothing else on the
network can read it — that is what the previous implementation did, and why a second
script could not run while the chat agent was open. `qdrant_vectors.py` only ever
constructs the client with a URL.

Everything happens server-side: an HNSW index, and filtering by `doc_id` through a keyword
payload index, so neither the vectors nor the payloads are dragged across the wire to be
scored here.

Point ids are `uuid5(doc_id:page_number:chunk_index)` — deterministic, so re-ingesting a
document overwrites its points in place instead of appending a second copy.

### MongoDB — everything else

| Collection | Holds |
| --- | --- |
| `documents` | One record per PDF: filename, SHA-256, page/chunk counts, GridFS pointer |
| `pdfs.files` / `pdfs.chunks` | The PDF bytes themselves, in GridFS |
| `pages` | Cleaned full text of each page, keyed by `(doc_id, page_number)` |
| `resources` | Generated content, the accepted flag, the score, and every attempt |
| `evaluations` | One row per verdict, tagged with which gate decided it |
| `chat_turns` | Chat history, keyed by `session_id` |

**A PDF's identity is the hash of its bytes, not its filename.** Re-uploading the same
document under a new name is recognised as one document, so the embedding work is not
repeated and every stored resource keeps pointing at a stable document.

### Swapping the vector backend

`LEARNMATE_VECTOR_BACKEND=mongodb` moves the vectors into MongoDB instead — a `chunks`
collection using Atlas `$vectorSearch` where it exists, and exact NumPy cosine where it
does not. It is there so the system can run without a second service; Qdrant is the better
choice whenever it is available.

Both backends return **raw cosine in [-1, 1]**, so `RELEVANCE_THRESHOLD` means one thing
either way. (Atlas reports cosine remapped to [0, 1] and is converted back, or the
threshold would silently mean two different things.) Verified: the same query returns
identical scores — 0.6830 / 0.6810 / 0.6805 — on both.

Switching backends does **not** migrate existing vectors. Re-run
`python cli.py ingest <pdf> --force`; the PDFs and page text are in MongoDB and are
untouched by this.

---

## Swapping in the finetuned model

The generator is reached through one interface with two interchangeable backends. Nothing
in the agents knows which is active.

**If the finetune ships as a GGUF file:**

```bash
LEARNMATE_GENERATOR_MODEL=models/my-finetune-q4_k_m.gguf
```

**If it is served over an OpenAI-compatible HTTP API** (e.g. from `finetuned-model-api/`):

```bash
LEARNMATE_GENERATOR_BACKEND=http
LEARNMATE_GENERATOR_API_URL=http://localhost:8001/v1
LEARNMATE_GENERATOR_MODEL=learnmate-finetuned
```

Two things to keep in mind:

- **Keep the judge a different model family from the generator.** A judge sharing the
  generator's weights rates its own output style highly and the retry loop stops firing.
- **Structured output matters.** Every generated resource depends on JSON-schema-constrained
  decoding. The `llamacpp` backend compiles the schema into a decoding grammar; the `http`
  backend forwards it as OpenAI `response_format`. If your server supports neither, output
  still parses through a fenced-JSON fallback, but expect more `parse`-stage failures in
  `python cli.py stats`.

---

## Commands

```
python cli.py doctor                                    check models, MongoDB, settings
python cli.py ingest <pdf> [--session ID] [--force]     store + index one PDF
              [--for chat|resource|both]                what the session is for
python cli.py docs                                      list ingested documents
python cli.py chat [--session ID] [--doc X] [--no-eval] interactive chat
python cli.py generate <task> [--session ID] [--doc X]  generate a resource
              [--count N] [--topic "..."] [--pages 3-7] [--json] [--no-eval]
python cli.py resources [--doc X] [--task T] [--show]   list what has been generated
python cli.py stats                                     score distribution per task
python cli.py export <doc> <destination>                write a stored PDF back to disk
python cli.py delete <doc>                              remove a document and its chunks
```

### One PDF per session, opened for one purpose

An upload always belongs to a session, and a session is opened for what you intend to do
with the PDF:

```
python cli.py ingest constitution.pdf --session s1                    # --for chat (default)
python cli.py ingest constitution.pdf --session s2 --for resource     # MCQs, summaries
python cli.py ingest constitution.pdf --session s3 --for both
```

Both purposes need identical ingestion -- the same chunks for retrieval and the same
stored page text for reading -- so the kind is a statement of intent, not an optimisation.
It is checked when a command runs, so using a session for the other purpose says so
plainly instead of quietly doing something you did not set up:

```
$ python cli.py generate mcq --session s1
[!] Session 's1' was opened for chat, not resource generation.
    Open one for resource generation on the same PDF -- already ingested, so nothing
    is re-embedded:
        python cli.py ingest constitution.pdf --session <new-session-id> --for resource
```

That advice is cheap to follow: the PDF is already stored and embedded, so the second
ingest takes the "already ingested" path and only writes the new binding.

A session also holds exactly one PDF, no larger than `LEARNMATE_MAX_PDF_MB` (10 MB by
default). Ingesting a second, different PDF into the same session is refused:

```
$ python cli.py ingest companylaw.pdf --session s1
[!] Session 's1' is already about constitution.pdf. One PDF per session -- ingest
    companylaw.pdf into a new session instead:
        python cli.py ingest companylaw.pdf --session <new-session-id>
```

Embedding a document is the expensive step -- a few thousand chunks through a CPU
embedding model -- so both limits are checked before any of that work starts. Re-ingesting
a session's *own* PDF is still allowed, which is what makes `--force` re-indexing work.
`ingest` prints a generated session id when none is given. Set
`LEARNMATE_ONE_PDF_PER_SESSION=0` to lift the one-PDF rule.

`--doc` overrides the session's PDF for one command, and accepts an id, an exact filename,
or a unique fragment (`--doc constitution`). A fragment matching several documents is
rejected rather than guessed at.

### Choosing what a resource is generated from

A 300-page PDF does not fit in a 4k context window, so the interesting question is *which
part* to use:

| Flag | Source |
| --- | --- |
| `--topic "directors' duties"` | The pages whose text best matches the topic |
| `--pages 12-18` | Exactly those pages |
| *neither* | The opening of the document, up to `MAX_SOURCE_CHARS` |

**The unit is always a whole page, never the retrieved chunks themselves.** Chunks are
sized and overlapped for retrieval, so joining them back repeats ~150 characters at every
boundary and starts the passage mid-sentence — and a generator handed that writes questions
about the fragments. Retrieval picks *which* pages; the `pages` collection supplies the
prose. Pages are then emitted in reading order, because relevance order reads as
non-sequitur.

---

## Reading the evaluation log

```bash
python cli.py stats
```

Two tables. The first says **which gate decided each attempt** — a high `validator` count
means the generator is producing malformed output and the prompt needs work, not the
threshold. The second is the **judge's score distribution per task**, and the column that
matters is `distinct`: a judge whose scores cluster in a narrow band cannot separate good
from bad at *any* threshold, however it is set. That is a rubric problem, not a threshold
problem.

This exists because the judge is a 3B model and its scores were observed to be unstable —
two near-identical replies scored 1 and 90. Logging every verdict is what turns that from
an impression into something measurable.

### Judge calibration — what was measured

The judge's usefulness turned out to depend far more on **source quality** than on the
threshold. Generating from raw retrieved chunks (overlapping, starting mid-sentence, with
contents-page fragments mixed in) against generating from whole pages, same rubric, same
threshold of 70:

| Task | From chunks | From pages |
| --- | --- | --- |
| `mcq` | rejected twice by the structural gate | **80, passed first try** |
| `practice_qsn` | 40 → 40, failed | 40 → **80, passed on retry** |
| `summary` | 40 → 60, failed | 60 → **80, passed on retry** |
| `keypoints` | 40 → 40, failed | 40 → 60, still failing |

Nothing passed before; three of four pass now. If generated content is scoring badly, look
at what the generator was actually handed before touching the threshold.

`keypoints` remains the weak one. Its rubric penalises both near-duplication and missing
the central point, and a 3B generator tends to trade one for the other. If it needs to
pass, the options are `--threshold 55`, softening the *"one invented point puts the set
below 50"* cliff in `rubrics.py` so the judge grades on a slope rather than falling off a
ledge, or pointing `LEARNMATE_JUDGE_MODEL` at a larger GGUF.

Either way the loop still returns content: `accepted` records whether it was reviewed
clean, so a harsh judge costs a wasted regeneration, not a lost result.

---

## Layout

```
components-Dinura/
├── cli.py                      command line for everything
├── docker-compose.yml          the Qdrant server
├── learnmate/
│   ├── config.py               every tunable, all env-overridable
│   ├── llm/
│   │   ├── registry.py         get_generator_llm() + get_judge_llm(), the entry points
│   │   ├── llamacpp.py         a local GGUF, in-process, with JSON grammars
│   │   ├── http_api.py         a served OpenAI-compatible endpoint
│   │   ├── messages.py         LangChain messages <-> role/content dicts
│   │   ├── runtime.py          the GGUF weight cache, released cleanly at exit
│   │   ├── download.py         fetches a missing GGUF from Hugging Face
│   │   ├── json_output.py      parse_json_reply()
│   │   └── embeddings.py       MiniLM behind LangChain's Embeddings interface
│   ├── storage/
│   │   ├── mongo.py            connection + indexes
│   │   ├── pdf_store.py        GridFS PDF storage, hash-deduplicated
│   │   ├── vectors.py          picks the vector backend
│   │   ├── qdrant_vectors.py   LangChain VectorStore over a Qdrant server
│   │   ├── mongo_vectors.py    the same, over MongoDB (no second service)
│   │   └── content_store.py    resources, evaluations, chat history
│   ├── ingestion/
│   │   ├── clean.py            page extraction, furniture removal
│   │   ├── chunking.py         cleaned pages -> the chunks that get embedded
│   │   ├── sessions.py         session kinds, one-PDF-per-session, the binding
│   │   ├── pipeline.py         ingest_pdf() -- the order it all happens in
│   │   └── source_text.py      build_source_text() -- what a resource session reads
│   ├── evaluator/
│   │   ├── normalise.py        norm() -- comparison-safe text for gate 1
│   │   ├── mcq_rules.py        gate 1: per-question faults + set-wide biases
│   │   ├── text_rules.py       gate 1: summary, keypoints, practice questions
│   │   ├── validators.py       gate 1 dispatcher: validate(task, content)
│   │   ├── rubrics.py          gate 2: per-task grading criteria
│   │   ├── prompt.py           gate 2: system prompt + message assembly
│   │   ├── verdict.py          gate 2: schema, parsing, fail-closed verdicts
│   │   └── judge.py            gate 2: Judge.judge / judge_chat_reply
│   ├── resource_agent/
│   │   ├── task.py             the Task contract every resource type implements
│   │   ├── mcq.py              multiple-choice questions
│   │   ├── practice_qsn.py     short-answer practice questions
│   │   ├── keypoints.py        key points
│   │   ├── summary.py          summaries
│   │   ├── tasks.py            the registry of the four types
│   │   ├── state.py            ResourceState, passed between nodes
│   │   ├── generate.py         node 1  ask the generator (+ critique on retry)
│   │   ├── check.py            node 2  both evaluation gates
│   │   ├── routing.py                  the accept-or-retry branch
│   │   ├── persist.py          node 3  store the resource + attempt trail
│   │   ├── graph.py            the LangGraph wiring
│   │   └── agent.py            generate_resource(), the public entry point
│   └── chat_agent/
│       ├── state.py            ChatState, the state passed between nodes
│       ├── rewrite.py          node 1  resolve the follow-up question
│       ├── retrieve.py         node 2  search vectors, pick pdf or general mode
│       ├── generate.py         node 3  write the reply
│       ├── evaluate.py         node 4  judge it
│       ├── routing.py                  the accept-or-retry branch
│       ├── persist.py          node 5  save the turn
│       ├── prompts.py          the three system prompts
│       ├── helpers.py          logging, history-to-messages
│       ├── graph.py            the LangGraph wiring
│       └── agent.py            ChatAgent, the public entry point
├── models/                     the two GGUF files (gitignored)
├── data/raw_pdfs/              sample PDFs
└── legacy/                     the previous embedded-Qdrant implementation
```

`legacy/` is the earlier version, kept for reference. It used Qdrant in **embedded** mode —
`QdrantClient(path="./qdrant_data")`, a locked directory inside the repo — plus hand-rolled
orchestration. Same database, opposite deployment: the server it now talks to is the thing
that changed. Nothing in `learnmate/` imports it.

---

## Notes and limits

- **Ingestion drops table-of-contents and index pages.** Detected by dot leaders rather
  than page position, since the index at the back has the same shape as the contents at
  the front. Without this, a contents page matches almost any topical query and out-scores
  the article the question is actually about — and asked for questions about
  "fundamental rights", the generator gets a page of headings and writes questions about
  the page numbering.
- **Scanned PDFs are rejected** with a clear message. There is no OCR step; a PDF with no
  extractable text cannot be indexed.
- **Everything runs on CPU by default.** A judged chat turn is roughly 40 s and a judged
  resource ~60–180 s with two 3B models resident (~5 GB RAM). Set
  `LEARNMATE_N_GPU_LAYERS` to offload if you have the VRAM, or `--no-eval` to skip the
  judge while iterating on prompts.
- **The evaluator fails closed.** A judge that cannot be parsed or reached returns a
  failing verdict rather than an exception — silently passing unreviewed content through
  is the one outcome worth ruling out. The reason always travels in `reasoning`, so a
  failure stays visible instead of looking like a bad score.
- **Qdrant's on-disk format is not backward compatible.** Bumping the image tag more than
  a minor version or two will crash-loop the container (1.18 cannot read 1.12 storage).
  Recover with `docker compose down -v` and re-ingest — the vectors are derived data, and
  the PDFs and page text in MongoDB are untouched.
- **Port 6335, not 6333.** This machine already runs a separate Qdrant on 6333 for another
  project, so the compose file publishes 6335 and keeps the two corpora in different
  servers. Change both `docker-compose.yml` and `LEARNMATE_QDRANT_URL` to move it.
