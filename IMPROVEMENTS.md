# What's new in LearnMate: the classroom-scale improvements

This document explains, in plain language, the four improvements added to LearnMate for the
demo paper, why each one matters, how to turn it on, and where things stand.

Nothing here changes how the app behaves today. Every improvement is **off, or behaves exactly
as before, until you switch it on** in `integrated-backend/.env`.

---

## The one big idea

Until now, LearnMate was designed for **one student at a time**. The models run locally,
which is good for privacy, but a single answer takes 30–60 seconds on a laptop, and the
server answers one question at a time.

There was already a useful detail in the code: when two people upload the **same file**,
LearnMate stores it **once** (it recognises the file by its fingerprint, a SHA-256 hash). So
when a whole class uploads the same lecture notes, they are all talking to the **same
document**. And while revising, they ask **the same questions**.

The four improvements all build on that fact:

| # | Improvement | In one sentence | Area |
|---|---|---|---|
| 1 | **Smarter search** | Find the right paragraph more often, using keyword search *and* meaning search together, inside the database. | Information retrieval |
| 2 | **Answer reuse** | If a classmate already asked the same question and got a checked answer, give it instantly. | IR + scalability |
| 3 | **Serving many students at once** | Several workers can answer questions in parallel, and a crashed worker doesn't lose anyone's question. | Scalability + NoSQL |
| 4 | **Class insights** | A heatmap showing which pages of the notes the class struggles with. | Data mining + NoSQL |

---

## 1. Smarter search (hybrid retrieval)

### The problem

To answer a question, LearnMate first has to **find the right paragraphs** (called "chunks")
in the document. There are two ways to search:

- **Meaning search** (dense vectors / embeddings): good at understanding that *"fire an
  employee"* and *"terminate employment"* mean the same thing. Bad at exact terms like
  *"Section 12"* or *"Sherman Act"*.
- **Keyword search** (BM25): good at exact words and names. Bad at synonyms.

The old code did both, but in a clumsy way:

- It simply **glued the two lists together** without deciding which results were best.
- The keyword index lived **inside the Python server's memory**. Every server process had
  to rebuild it, and on every question it re-scored **every paragraph** of the document.
- The keyword search didn't understand word forms: *"duty"* and *"duties"* didn't match.

### What we changed

Both searches now run **inside Qdrant** (the vector database), in **one request**:

```
student question
      │
      ├── meaning search  (dense vectors)      ─┐
      │                                          ├─► combined by "Reciprocal Rank Fusion" (RRF)
      └── keyword search  (BM25 sparse vector) ─┘         │
                                                           ▼
                                   reranker picks the best 3 paragraphs → answer
```

- **Keyword search got proper text processing.** Common words ("the", "of") are ignored, and
  words are reduced to their root (*duties → duti*, *directors → director*) using the
  classic Porter stemmer.
- **The database now does the keyword maths.** It knows how rare each word is across all
  documents (the "IDF" part of BM25), so no server process needs to hold that in memory.
- **The two result lists are merged properly** with Reciprocal Rank Fusion: a paragraph
  ranked highly by *either* search ends up near the top.
- **Each search is limited to the student's own document**, which the database treats as a
  "tenant". That keeps searches fast even with thousands of documents.

### How to turn it on

Existing data has to be copied into the new format once. This takes minutes and **does not
re-read your PDFs**, and usually doesn't recompute the meaning vectors either:

```
cd integrated-backend
python scripts/reindex_qdrant.py
```

It prints the lines to add to `.env`, for example:

```
LEARNMATE_QDRANT_COLLECTION=learnmate_chunks_v2
LEARNMATE_RETRIEVAL_STRATEGY=rrf
LEARNMATE_QDRANT_SCHEMA=v2
```

If anything is misconfigured, it automatically falls back to the old search. A search
problem can never lose a student's answer.

**Code:** `learnmate/retrieval/` (analyzer, sparse vectors, fusion, retriever),
`learnmate/storage/qdrant_vectors.py`, `scripts/reindex_qdrant.py`.

---

## 2. Answer reuse (the verified answer cache)

### The problem

If 30 students ask *"What makes a contract enforceable?"*, the laptop generates the answer
30 times, at 30–60 seconds each, even though the answer is the same every time.

### The obvious fix, and why it's dangerous

"Save answers, and if a new question is *similar* to an old one, reuse the old answer."
That is called a **semantic cache**. The danger is that questions can look almost identical
and still need **different** answers:

- *"What are the **advantages** of a sole proprietorship?"*
- *"What are the **disadvantages** of a sole proprietorship?"*

To a meaning-search model these two look ~95% the same. Reusing one answer for the other
would give a student a wrong answer.

### What we built: a cache with a second check

```
new question
   │
   ▼
1. find the 3 most similar questions already answered for THIS document   (fast, rough)
   │   similar enough?  no → answer normally
   ▼
2. ask a second model: "are these two questions really the same question?"  (careful)
   │   no → answer normally
   ▼
3. yes → reuse the saved answer instantly, with its page citations
```

The second model is a small "duplicate question detector", trained on a large public set of
question pairs from Quora. In a quick spot-check it scored the advantages/disadvantages pair
at **0.02** (clearly different) and a genuine rewording at **0.90** (the same).

It is also **strict**: one real rewording ("What is consideration in contract law?" vs
"What does consideration mean for a contract?") scored only 0.27. So it will sometimes
*miss* a chance to reuse an answer. That only costs a slower answer, never a wrong one. The
benchmark picks the exact thresholds from measured data.

Rules that keep it safe:

- **Only answers the judge model approved are saved.** Nothing unchecked is ever reused.
- **Only answers based on the document** are saved, not "general knowledge" answers.
- **Follow-up questions** like *"what about his powers?"* are not saved, because their
  meaning depends on the earlier conversation.
- If the document is **re-uploaded or deleted**, its saved answers are thrown away.
- Saved answers expire after two weeks.
- **No student names or IDs are stored** with a saved answer. It records only the question,
  the answer and the document.

### What students see

A reused answer shows a green badge: **"Verified answer reused · 3 h ago"**. Hovering it
shows how similar the questions were. Students are never misled about where an answer came
from.

### How to turn it on

```
LEARNMATE_CACHE_ENABLED=1
```

**Code:** `learnmate/cache/answer_cache.py`, `learnmate/llm/equivalence.py`,
`learnmate/chat_agent/cache_nodes.py`, and the badge in
`integrated-frontend/src/components/ChatMessage.jsx`.

---

## 3. Serving many students at once (job queue + worker pool)

### The problem

Every slow task (answering a question, processing a PDF, generating a quiz) is a **job**.
The old design had:

- **One worker** handling jobs one by one. If 10 students ask at once, the 10th waits for
  the other 9.
- **The queue in memory.** If the server restarted, every waiting job was lost and marked
  failed.
- Only **one server process** could run against the database. Starting a second one would
  mark the first one's jobs as failed.

The single worker was **correct** at the time. The AI model ran *inside* the server
process, and it can only do one thing at a time. That's still true in that mode.

### What we built

**(a) The queue now lives in MongoDB, with "leases".**

Think of each job as a library book:

1. A worker **checks the job out** with a single, atomic database operation, so two workers
   can never take the same job.
2. The checkout comes with a **lease**, a due time (60 seconds).
3. While working, the worker **renews the lease** every 15 seconds ("still working on it").
4. If a worker **crashes**, it stops renewing. When the lease runs out, a "reaper" puts the
   job **back on the shelf** and another worker picks it up. After too many failed attempts
   the job is marked failed, so a broken job can't crash every worker in turn.

The due times use the **database's clock**, so workers on different computers always agree
on when a lease has run out. And a retried chat question can't be saved twice, because the
database rejects a second copy.

**(b) Many workers.** You can run several worker threads, and also separate **worker
processes** with no website attached (`python -m app.jobs.worker_main`), even on other
machines.

**(c) The models move into their own servers.** `llama-server` (from llama.cpp) runs each
model with several **parallel slots**. It uses **continuous batching**: it processes the
words of several students' answers in the same step, so four answers at once take much
less than four times as long.

```
students ──► API ──► MongoDB job queue ──► worker 1 ─┐
                                        ──► worker 2 ─┼──► llama-server (generator, 4 slots)
                                        ──► worker 3 ─┤──► llama-server (judge, 4 slots)
                                        ──► worker 4 ─┘
```

Safety: if the models still run *inside* the server process, the code **forces one worker**,
so the old correctness rule can't be broken by a config mistake.

### How to turn it on

```
# 1. start the model servers (Mac):   SLOTS=4 scripts/serve/llama_servers.sh
# 2. in .env:
LEARNMATE_GENERATOR_BACKEND=http
LEARNMATE_JUDGE_BACKEND=http
JOB_QUEUE_BACKEND=mongo
JOB_WORKERS=4
# 3. check the model servers work:     python scripts/serve/probe.py
```

`/api/health` now also shows the queue: which kind, how many workers, and how many jobs
are waiting or running.

**Code:** `app/jobs/queue.py`, `app/jobs/worker.py`, `app/jobs/worker_main.py`,
`learnmate/storage/jobs.py`, `learnmate/llm/http_api.py`, `scripts/serve/`.

---

## 4. Class insights (the confusion heatmap)

### The idea

Every question a student asks about the shared notes is a small signal about **the notes
themselves**. If many students ask about page 12, and the answers are poor or they keep
asking again, page 12 is probably explained badly. That's useful for students and very
useful for a lecturer.

### How it works

```
all students' questions about one document   (stored in MongoDB)
        │
        ▼
1. MongoDB counts per page, inside the database   ("aggregation pipelines")
        │
        ▼
2. group similar questions into topics            (embeddings + HDBSCAN clustering)
        │
        ▼
3. name each topic with its most telling words    (class-based TF-IDF, as BERTopic does)
        │
        ▼
4. give each page a "confusion score" and hide anything too small to be anonymous
        │
        ▼
heatmap in the app
```

A page's **confusion score** combines how many questions it gets with four warning signs:

| Warning sign | Meaning |
|---|---|
| Not in the notes | The document couldn't answer questions about it. |
| Low score | The judge model rated the answers poorly. |
| Rejected | Even the retry didn't produce a good enough answer. |
| Asked again | The same student came back to the same topic within a week. |

A question is linked to the page its answer cited. If the document couldn't answer it, it's
linked to the page the search came closest to, because that page didn't cover the question.

### Privacy

- It shows **only totals and topic keywords**, never anyone's actual question.
- A page or topic is **hidden until at least 3 different students** contributed to it
  (called *k-anonymity*). Otherwise "one question about page 12" could point to one
  person. Hidden pages appear as striped cells.
- No names or IDs are ever shown.

### What you see

- In the **Library workspace**, there's a new third tab, **"Class insights"**: a strip of page
  squares (darker means more confusion), and below it the topics the class asks about, with
  badges like "40% not in the notes". **Click a page square and the document jumps to that
  page.**
- On the **Analytics** page, a new card, **"Where the class gets stuck"**, with a document
  picker.

It's on by default, and it's read-only (it only reads data that already exists).

**Code:** `learnmate/insights/` (aggregate, cluster, confusion, service), the new
endpoint `GET /api/analytics/documents/{id}/heatmap`, and
`integrated-frontend/src/components/ConfusionHeatmap.jsx`.

---

## How we prove it works: the evaluation

A research paper needs **measured** numbers. None of the paper's numbers are typed by
hand. They all come from scripts in `integrated-backend/eval/`, and each result file
records which code version and which computer produced it. (This matters because the old
`screenshots/` folder contains mock-ups with made-up numbers. The paper must not use those.)

### The test material

- **Documents:** 8 chapters of an open law textbook, *Business Law I Essentials* (OpenStax),
  each uploaded as one "shared notes" document: 341 paragraphs in total.
- **Questions:** the local AI model reads sample paragraphs and writes, for each one:
  - a student-style question it answers,
  - two rewordings of that same question,
  - a "near miss": a question on the same topic that needs a *different* answer.

  We know exactly which paragraph each question came from, so search results can be marked
  right or wrong automatically. The rewordings test answer reuse, and the near misses test
  that reuse doesn't go wrong.
- **A simulated class:** 40 students each ask questions about 2 chapters over two weeks.
  A few questions are very popular (as in real life), and students word things differently.

### What each script measures

| Script | Question it answers |
|---|---|
| `ir_bench.py` | Does the new search find the right paragraph more often? Is it fast? |
| `ir_scaling.py` | What happens to search speed as documents get bigger, or there are more of them? |
| `cache_bench.py` | How often is a reused answer correct, and how often is one available? |
| `cache_replay.py` | Over two weeks of class questions, what share gets an instant reused answer? |
| `chat_latency.py` | How long does a full answer take vs a reused one? |
| `load_test.py` | With many students at once, how many answers per minute, and how long is the wait? |
| `heatmap_bench.py` | Does question mining find the right topics and pages? |
| `tables.py` | Turns all results into the paper's tables and numbers. |

### Isolation: the tests never touch real data

The tests use a **separate database** (`learnmate_eval`) and a **separate Qdrant container**
(`learnmate-eval-qdrant` on port 6337). Your app's data and your running Docker deployment
are never touched.

---

## The paper

Everything is in the `paper/` folder:

| File | What it is |
|---|---|
| `main.tex` | The paper, in the official ACL style (6 pages). Written for the ACL/EMNLP *System Demonstrations* track. |
| `references.bib` | 32 references. The less familiar ones (the caching papers, the textbook) were checked online; re-check all page numbers against the ACL Anthology or DBLP before submitting. |
| `figures/architecture.tex` | The system diagram (drawn in LaTeX). |
| `tables/` | Filled in automatically by `python -m eval.tables`. |
| `screencast.md` | A second-by-second script for the required 2.5-minute demo video. |
| `tools/capture_screens.py` | Takes the paper's screenshots from the real running app. |

In the paper, a number that hasn't been measured yet shows as **??**, so it can't contain
an invented number.

To build the PDF (MiKTeX is installed; `latexmk` needs Perl, so run the steps directly):

```
cd paper
pdflatex main && bibtex main && pdflatex main && pdflatex main
```

---

## Verified end to end (2026-09-21)

The whole app was run on this laptop against throwaway stores (a separate database and a
separate Qdrant collection, deleted afterwards), in three configurations, plus a real browser:

| Check | Result |
|---|---|
| **Default settings** (nothing new switched on): the existing 29-step smoke test (accounts, upload, ingest, key points, MCQs, chat, follow-up rewrite, access control, analytics) | 29/29 pass: no regressions |
| **All new features on** (RRF search, answer cache, MongoDB queue): the same smoke test | 29/29 pass |
| Grounded answer through the new search | pdf mode, rerank score 0.96, judge 80/100, page citations |
| Answer reuse, exact repeat | served in **0.34 s** (a full answer takes ~60 s), same citations |
| Answer reuse, close rewording | similarity 0.96, checker 0.97, served from the cache |
| Near-miss question ("when is a contract *not* enforceable…") | not served from the cache |
| `use_cache: false` | skips the cache as intended |
| A looser rewording (similarity 0.68) | missed at the temporary threshold 0.80: exactly what `cache_bench` is there to tune |
| Safety rule: 2 workers requested while models run in-process | forced to 1, with a warning in the log |
| **Served models** (llama-server, 2 slots each): JSON-schema output | 10/10 valid for both generator and judge |
| Continuous batching on this CPU | 2 concurrent requests: ~30% more tokens per second |
| **Two worker processes**, API only enqueuing | two students' questions claimed by different workers and answered at the same time |
| **Crash test:** kill the worker holding a job mid-answer | job requeued after its lease ran out, finished by the other worker 27 s later on attempt 2, saved exactly once |
| **Frontend in Microsoft Edge** (dashboard, library, workspace tabs, class insights, chat, analytics, resources, dark mode) | 11/11 checks pass, no console errors, no failed API calls |
| Frontend lint and production build; backend unit tests | clean; 105 pass (+3 run against real MongoDB) |

One problem was found and fixed during this run: in the workspace, clicking a page in the
heatmap scrolled the **whole window**, pushing the heatmap out of view. On desktop the two
workspace panes now scroll independently, and the reader jumps to the page inside its own pane.

---

## Current status

| Part | Status |
|---|---|
| Improvement 1: smarter search | ✅ Built, tested, and run against the real database |
| Improvement 2: answer reuse | ✅ Built and tested; the checker model downloaded and spot-checked |
| Improvement 3: queue + workers | ✅ Built and tested, including 3 tests on the real MongoDB (60 jobs, 4 workers competing: each job taken exactly once) |
| Improvement 4: class insights | ✅ Built and tested; frontend builds and lints cleanly |
| Automated tests | ✅ 108 backend unit tests pass (existing + new). Separately, 3 older Word/PowerPoint tests fail only because `python-pptx` isn't installed in the venv; that predates this work. |
| Test documents | ✅ 8 chapters loaded into the test database |
| Test questions | ⏳ 70 of ~126 written (~30 s each on this laptop's CPU); paused during verification and resumed afterwards |
| Running the benchmarks | ⏳ Next, once the questions are done, on an otherwise idle machine |
| Paper text | 📝 Drafted; the results section is written only after the real numbers are in |
| Screenshots | ⏳ After the benchmarks |

### Still needed from you

1. **Author names and affiliations** in `paper/main.tex` (currently placeholders).
2. **Repository link and video link** (the paper has a footnote for them).
3. **Record the 2.5-minute screencast**, following `paper/screencast.md`.
4. **Decide the venue and deadline.** ACL 2026's demo deadline has passed. The same format
   applies to the next ACL-family demo tracks (EACL/NAACL/ACL 2027). Check the call you pick.
5. For the best speed numbers, **run the serving tests on the M4 Pro Mac** (Metal GPU). The
   laptop numbers will be clearly labelled as CPU-only.

---

## Things done outside the code (so nothing surprises you)

- **Started a Docker container**, `learnmate-eval-qdrant` (port 6337, local only), just for
  the tests. Remove it any time with `docker rm -f learnmate-eval-qdrant`.
- **Did not touch** your running deployment stack (`learnmate-backend`, `learnmate-frontend`,
  `learnmate-qdrant` from the root `docker-compose.yml`).
- **Downloaded** the official llama.cpp Windows build (b11062) into
  `integrated-backend/data/tools/` for the serving test. It's git-ignored.
- **Downloaded the textbook** into `integrated-backend/data/eval_corpus/` (git-ignored). Note
  that its licence is **CC BY-NC-SA 4.0** (non-commercial, share-alike), not plain CC BY.
  Research use is fine; don't redistribute the PDFs.
- **Updated `.gitignore`** so test documents, generated questions, downloaded tools and
  LaTeX build files are never committed. Test *results* are kept, because they back up the
  paper's numbers.
- **Documented every new setting** in `integrated-backend/.env.example` (section
  *CLASSROOM SCALE*) and in `integrated-backend/README.md`.
- Nothing has been committed or pushed.

---

## Words used in this document

| Term | Meaning |
|---|---|
| **Chunk** | A paragraph-sized piece of a document (up to 900 characters) that search works on. |
| **Embedding / dense vector** | A list of numbers representing a text's *meaning*; similar meanings have similar numbers. |
| **BM25** | The classic keyword-search scoring formula: rare words that appear often in a paragraph score high. |
| **Sparse vector** | A way to store "which words appear, and how important they are" so a database can search it. |
| **IDF** | "Inverse document frequency": how rare a word is. Rare words matter more. |
| **Stemming** | Cutting words to their root so *duty*, *duties* and *dutiful* match. |
| **RRF (Reciprocal Rank Fusion)** | A simple, robust way to merge two ranked lists into one. |
| **Reranker / cross-encoder** | A slower, more careful model that reads the question and a paragraph *together* to judge the match. |
| **Semantic cache** | Saving answers and reusing them for questions with the same meaning. |
| **Lease** | A time-limited claim on a job that must be renewed, so crashed workers' jobs come back. |
| **Continuous batching** | A model server handling several requests' words in the same step. |
| **HDBSCAN** | A clustering method that finds groups without being told how many there are, and leaves outliers alone. |
| **c-TF-IDF** | Picks the words that best describe one group compared with the others (used for topic labels). |
| **k-anonymity** | Only showing a statistic when at least *k* different people contributed to it. |
| **Judge model** | The second AI model (Llama 3.2 3B) that grades each answer from 1 to 100. |
