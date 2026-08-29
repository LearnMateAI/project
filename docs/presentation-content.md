# LearnMateAI — presentation content

Per slide: the text to write, and the screenshot or visual to drop in.

Everything here is taken from the actual codebase, so the numbers are real and safe to
say out loud. Keep slide text short — the sentences in *italics* are what you say, not
what you put on the slide.

**Setup before screenshotting:** start the stack (`docker compose up -d` in
`integrated-backend/`, backend on `:8010`, frontend on `:5173`), sign in, upload two or
three PDFs with different subjects, generate at least one of each resource type, and have
one chat conversation. A half-empty app screenshots badly.

---

## 1 — Cover

**Title:** LearnMateAI
**Subtitle:** An E-Learning Platform for Self-Learning Using Large Language Models
**Line 3:** Semester 5 · Group Project · Group 8
**Names:** Dinura N. Ginige · Tharumini Gamage · Thevindu Fernando
**Tagline (optional):** Every model runs locally. No uploaded document ever leaves the machine.

**Screenshot:** none. Keep it typographic — a dark or white cover with just the title.
If you want an image, use the app logo/wordmark from the sidebar.

---

## 2 — Problem statement

**Title:** A PDF cannot be asked a question

- **Lecture material is static.** It can be read start to finish, but not interrogated, quizzed against, or summarised on demand.
- **General chatbots answer from the internet.** Not from your lecture notes — and with no page you can turn to and check.
- **Generated study material is unverified.** An MCQ with the wrong option marked correct teaches the wrong thing, confidently.
- **Course material is sensitive.** Uploading a department's notes to a cloud model is a privacy question most institutions cannot answer.
- **Sri Lankan legal education in particular** has very little digitised, subject-aligned material to study from.

**Closing box:** Material a student studies from has to be traceable to its source and checked before delivery. Without both, a generated summary and a confident guess look identical from the outside.

**Screenshot:** none — this slide is stronger as text. If you want a visual, put a plain
PDF page next to a chat bubble with no citation, as a "before" picture.

---

## 3 — About

**Title:** What LearnMateAI does

**Lead line:** Upload a PDF. Ask it questions and get answers that cite the pages they came from, or generate study material from it. Everything the system produces is graded by a second model before it reaches you.

Four boxes:

| | |
|---|---|
| **01 Upload** | Validate, extract, clean, chunk and embed a PDF into a searchable index. Page numbers survive the whole pipeline — they are what citations point at. |
| **02 Ask** | Answers built from the retrieved passages, carrying the pages they came from. A question the document does not cover is answered separately, without citations. |
| **03 Generate** | Summary, key points, MCQs and short-answer practice questions — from one passage or pooled across the whole document. |
| **04 Judge** | Structural validators first, then a second model from a different family grades the output and can send it back for one more attempt. |

**Number strip:** 2 × 3B local models · 10 + 1 MongoDB collections · 4 resource types · 70/100 the judge score an output must clear

**Screenshot:** `http://localhost:5173/` — the **Home page**, full window. It already shows
the product in one frame. Alternative: `/tour` (Take a Tour).

---

## 4 — Architecture (overall)

**Title:** One machine, four moving parts

**Lead line:** React talks to FastAPI over JSON and a bearer token. The backend is split into a web layer and an engine that knows nothing about HTTP.

Three columns:

- **Client — integrated-frontend.** React 19 · Vite 8 · Tailwind 4 · React Router 7 · axios with two interceptors · `useJob` polls a 202 to done.
- **Server — integrated-backend, FastAPI.** `app/` = the web layer (routers, services, auth, jobs, ownership). `learnmate/` = the engine (ingestion, agents, evaluator, storage).
- **Behind it.** MongoDB 8 `:27018` (10 collections + GridFS) · Qdrant 1.18 `:6335` (chunk vectors, HNSW) · Local models (2 × Q4 GGUF via llama.cpp) · Keycloak 26 `:8081` (realm, JWKS, login theme).

**Bottom box — "Everything slow is a job":** Local inference on a 3B model takes tens of seconds, so no slow endpoint holds a connection open. Upload, generation and chat each answer `202` with a job id, and the client polls `/api/jobs/{id}` through queued → running → done. The queue lives in MongoDB, not in memory, so reloading the page does not lose your place. One worker thread — because `llama_cpp.Llama` holds a single mutable context, and two threads generating at once corrupt both replies.

**Visual:** you already have a diagram — export `docs/component-2.drawio` (or use
`docs/Component Diagram.pdf`) as PNG. Don't screenshot code for this one.
**Backup screenshot:** `docker compose ps` in the terminal, showing all three containers
healthy — good proof the whole stack is real.

---

## 5 — Group approach

**Title:** Three tracks, merged on main

**Lead line:** Each member built their part as a standalone component first. Work landed on feature branches and pull requests into `main`, then the pieces were integrated into one application.

| Member | Track | Work |
|---|---|---|
| **Dinura N. Ginige** | Engine & integration | Chat agent and resource agent as LangGraph state machines · evaluator (validators + LLM judge) · retrieval, embeddings, reranking · `app/` layer: auth, jobs, ownership · integration of all components · frontend shell and design system |
| **Tharumini Gamage** | Documents & resources | PDF document-processing pipeline · resource generator service · backend API and database work · frontend pages and layouts |
| **Thevindu Fernando** | Offline ML track | Sri Lankan legal corpus → instruction pairs · LoRA/QLoRA fine-tune of Qwen 2.5 · evaluation gate and version registry · MLOps promote/rollback workflow |

**Footnote:** The standalone components — `components-Dinura/`, `backend/`, `frontend/` — are kept frozen as references. The live application is `integrated-backend/` + `integrated-frontend/`. `model-Thevindu/` stays out of the request path by design.

**Screenshot:** the GitHub **repository Insights → Contributors graph**, or the
**Pull requests (Closed)** list showing the merges from `dinura-work`, `tharumini-dev`
and `thevindu-dev`. Either one proves the branch-and-PR workflow in a single image.

---

## 6 — Data preprocessing, cleaning and representation

**Title:** From a PDF to something a model can search

**Pipeline (one row, arrows between):**
`Validate` → `Extract` → `Clean` → `Chunk` → `Embed`
(PDF · ≤10 MB · ≤300 pp) — (PyMuPDF, page by page) — (heads · ligatures · hyphens) — (900 chars / 150 overlap) — (MiniLM → Qdrant)

**What cleaning removes**
- Running heads and footers repeated on every page
- Ligatures rejoined into plain letters
- Hyphenation reconnected across line breaks
- Chunks under 80 characters dropped as noise

**How a document is represented**
- `pages` — cleaned page text, what the models actually read
- `chunks` — 900-character overlapping windows, split on sentence and paragraph boundaries
- Qdrant — one 384-dimension vector per chunk, HNSW index
- GridFS — the original file, so text and PDF cannot be separated

**Bottom box — stored once:** Documents are keyed by the SHA-256 of their bytes, so a file ten students upload is extracted and embedded a single time. That is also why ownership cannot be a field on the document and lives in `user_documents` instead.

**Screenshot:** the **Qdrant dashboard** at `http://localhost:6335/dashboard` → your
collection → the **Points** view, showing chunk payloads and vector counts. That single
image makes "chunks became vectors" concrete.
**Optional second image:** a before/after of one paragraph — raw PyMuPDF text with a
running head and a hyphen break, next to the cleaned version.

---

## 7 — Models used (1 of 3): the generator

**Title:** The generator — Qwen2.5-3B-Instruct

**Lead line:** Writes every chat reply and every piece of study material. Runs in-process through llama.cpp — no API key, no network call.

| Property | Value |
|---|---|
| Model | Qwen2.5-3B-Instruct |
| Format | Q4 quantised GGUF, ≈ 2 GB on disk |
| Runtime | llama-cpp-python 0.3, inside the API process |
| Source text per call | ≤ 6 000 characters of retrieved passage |
| Chat history carried | 6 turns |
| Attempts | 2 — one regeneration on a rejection |

**Why this model**
- 3B fits an ordinary laptop, and Q4 quantisation makes it about a quarter of the size for a small loss in quality
- Grammar-constrained decoding forces valid JSON — asked politely, a 3B model returns prose about half the time
- Instruction-tuned, so a prompt describing the task works without few-shot examples

**Bottom box — three interchangeable backends:** llama.cpp (default, fully local), a served HTTP endpoint, or a cloud API. Our wrapper implements LangChain's `BaseChatModel` interface, so swapping the generator is two lines of `.env` and no code change. The cloud path is an *availability* fallback — process down, timeout, missing pointer — never a per-answer quality router.

**Screenshot:** `http://localhost:8010/api/health` in the browser — the JSON showing both
model files and both databases reporting separately. Clean, small, and proves it's local.
**Alternative:** the backend terminal at startup, showing the llama.cpp load lines
(model name, quantisation, context size).

---

## 8 — Models used (2 of 3): the judge

**Title:** The judge — Llama-3.2-3B-Instruct

**Lead line:** Grades what the generator wrote against the passage it was given, and says what to fix.

**Gate 1 — structural validators (no model involved).** Decidable in plain Python in microseconds: an MCQ has four options and exactly one marked answer, a summary is present and long enough, a practice answer is not a restatement of its question. Catching these here means the ≈25-second judge call is only ever spent on well-formed content.

**Gate 2 — the judge.** A per-task rubric — one each for MCQ, practice questions, key points and summary, plus two more for grounded and general chat replies. Below 70 the judge returns an instruction and the generator gets one more attempt; the better of the two is what the student sees.

**Why a different model family.** A model grading its own writing rates its own style highly, and the quality check quietly stops catching anything. Different weights means a genuine second opinion rather than a rubber stamp.

**A chat reply skips gate 1.** There is nothing mechanical to check in free prose, so a chat answer goes straight to the judge.

**Bottom box:** Every verdict is logged — passes as well as failures — into the `evaluations` collection. That is what turns "how good is the material this produced" from an impression into a question with an answer.

**Screenshot:** **MongoDB Compass** on `mongodb://localhost:27018` → the `evaluations`
collection, one document expanded so the score, the stage and the judge's reason are
visible. This is the most convincing single image in the whole deck — use it.

---

## 9 — Models used (3 of 3): retrieval

**Title:** Retrieval — a fast model and an accurate one

**Lead line:** Finding the right passage takes two stages, because the model that can search everything and the model that judges a pair are not the same model.

**Flow:** `Question` → `Bi-encoder (all-MiniLM-L6-v2)` → `Qdrant ANN — 20 candidates` → `Cross-encoder (ms-marco-MiniLM-L-6-v2)` → `Top 3 chunks into the prompt`

- **Stage 1 — bi-encoder, ≈90 MB (recall).** Encodes every chunk once at upload and the question at query time, then compares vectors. It never sees the question and the chunk together — which is exactly why it is fast enough to search thousands of chunks in milliseconds.
- **Stage 2 — cross-encoder, ≈90 MB (precision).** Reads the question and one candidate chunk together and scores the pair. Far more accurate and far too slow to run over a corpus — so it only reorders the 20 the first stage found.

**Bottom box:** The reranker can only reorder what retrieval found, so the 20 candidates are the real recall ceiling — `TOP_K = 3` is merely how much of the reordered list reaches the prompt. A chunk scoring below 0.5 is dropped rather than padded in.

**Screenshot:** a **chat answer with its page citations expanded** at `/chat` — showing
which pages the answer was built from. That is the retrieval result made visible.

---

## 10 — Databases used

**Title:** Three stores, three jobs

| Store | Port | What it holds |
|---|---|---|
| **MongoDB 8** | `:27018` | Everything that is not a vector. The records genuinely differ in shape — an MCQ, a summary and a chat turn are not the same thing — so a document database stores them without inventing a table for each. |
| **Qdrant 1.18** | `:6335` | One collection of chunk vectors. Answers "which passages are closest in meaning to this question" in milliseconds using an HNSW index, rather than comparing against every chunk one at a time. |
| **Keycloak 26** | `:8081` | The identity store: the `learnmate` realm, its public client and its users, imported from JSON the first time the volume is empty. |

**The ten collections, plus the file bucket:**
`users` · `user_documents` · `documents` · `pages` · `chunks` · `sessions` · `chat_turns` · `resources` · `evaluations` · `jobs` · `pdfs` (GridFS)

**Bottom box — why the ports are unusual:** All three publish on non-default host ports. This machine already answers on 27017, 6333 and 8080 for other projects — and sharing a database server means sharing a failure: another project's `docker compose down -v` would take this one's PDFs, sessions and generated resources with it. Each has its own container and its own named volume.

**Screenshot:** **MongoDB Compass** showing the database with all ten collections and
their document counts in the left panel. Add a small inset of the **Qdrant dashboard**
collection view if there's room.

---

## 11 — ML and fine-tuned LLM

**Title:** Two ML stories, kept apart

**Lead line:** The live path runs on every request. The offline fine-tune has never been in the request path, and will not be until it passes its gate.

**Offline track — `model-Thevindu/`, six stages**
1. Parse, clean and section-aware chunking of Sri Lankan legal PDFs
2. Instruction pairs: Q&A, summary, MCQ
3. Splits by `(doc_id, chapter)`, plus a whole-document holdout
4. LoRA / QLoRA on Qwen2.5-1.5B-Instruct, Colab T4
5. Evaluated against `acceptance_thresholds.yaml`
6. Staging → teammate sign-off → promote a pointer, rollback kept

**First candidate — `qwen25-lora-20260815-090709`**

| Metric | chapter test | strict test | Gate |
|---|---|---|---|
| Accuracy (LLM judge) | 0.557 | 0.621 | ≥ 0.70 — **fail** |
| Groundedness | 0.877 | 0.921 | ≥ 0.85 — pass |
| Hallucination | 0.123 | 0.079 | ≤ 0.15 — pass |
| Latency p95 | 16.4 s | 14.9 s | ≤ 8 s — **fail** |
| Accuracy (token-F1) | 0.717 | 0.836 | proxy only |

**Bottom box — the gate did its job:** Token-F1 of 0.717 looked like a pass; the LLM judge — the metric that matches how the live app defines correctness — did not agree. So the candidate was not promoted and the local GGUF generator stays. Two dataset defects were caught the same way: ungrounded section citations (≈38% of pairs on a spot check, 1.0% rejected after the fix) and a split that left six subjects with no training pairs at all.

> Present the failure as the result. A gate that catches your own model is a stronger
> finding than a green number, and it is the honest reading of the data you have.

**Screenshot:** `model-Thevindu/03_testing_and_versioning/version_registry.csv` opened in
Excel or VS Code, with the FAIL row visible. Add the **Colab training run** (loss curve or
the final `trainer` output cell) from `02_finetuning/finetune_qwen25_lora.ipynb` beside it.

---

## 12 — Dashboard

**Title:** The first screen after signing in

**Lead line:** What to do next, and what you were last working on — in that order.

- **Quick start** — the three things there are to do, as links: upload a document, ask your documents, generate study material
- **Recent resources** — the latest generated material with its verdict, and anything still running shown above what has finished
- **Your documents** — recent uploads with their Processing or Ready state, so the next step is always visible
- **Straight to work** — a returning student's first action is one click from sign-in

**Screenshot:** `http://localhost:5173/dashboard`, full window, **with real data in it** —
at least two finished resources and one document. Take it at a normal browser zoom so the
sidebar, topbar and cards all fit.

---

## 13 — Upload PDF

**Title:** Drop a file and keep working

**Lead line:** The row appears immediately and turns Ready on its own. The page watches the job, so there is nothing to refresh and nothing to wait on.

**Flow:** `Drop a PDF (and pick a subject)` → `202 + job id returned at once` → `Processing — the row is already there` → `Worker: validate → … → embed` → `Ready — the row flips itself`

**Limits, and what is rejected**
- PDF only, up to 10 MB and 300 pages
- Encrypted or corrupt files are caught at validation and explained, not left to fail somewhere deeper
- A subject label is chosen at upload and travels with the document

**What the worker does with it**
- Extract page text, clean it, chunk it, embed it into Qdrant
- Store the original file in GridFS and the cleaned text in MongoDB
- Report progress per stage, so the job is legible while it runs

**Bottom box:** A repeat upload is nearly instant. Documents are keyed by the SHA-256 of their bytes, so if somebody has already uploaded that exact file the extraction and embedding are skipped entirely — only the ownership link is new.

**Screenshot:** two images side by side from `/documents` — **(a)** the upload panel with a
file being dropped and the subject selector open, **(b)** the document list with one row
showing **Processing** and the others **Ready**. The two-state pair is the whole point of
the slide.

---

## 14 — Chat agent architecture

**Title:** One chat turn is one graph pass

**Lead line:** A LangGraph state machine rather than one long function — because the interesting part is the edge that loops back.

**The graph:**
`rewrite` → `retrieve` → `generate` → `evaluate` → `decide` → `persist`
with an arrow from `decide` back to `generate`, labelled **regenerate once with the judge's instruction · MAX_ATTEMPTS = 2**

| Node | Does |
|---|---|
| rewrite | resolve "it", "that case" against the conversation |
| retrieve | embed → ANN search → rerank |
| generate | answer from the retrieved chunks |
| evaluate | structural validators, then the judge |
| decide | accept, or send it back once |
| persist | store the turn |

**Two milestones in one turn.** Tokens stream onto `progress.partial` as they arrive, then `reply_ready` hands over a finished, readable answer while the judge runs off-screen. A regeneration is deliberately *not* streamed over it — replacing a finished paragraph with a half-written one reads as the assistant having second thoughts in public.

**Grounded, or honestly not.** An answer built from retrieved chunks carries the pages it came from. A question the document does not cover is answered from general knowledge instead — a different kind of answer, graded on a different rubric, carrying no citations, so the difference is visible rather than hidden.

**Footnote:** Resource generation is a second graph in `learnmate/resource_agent/` with the same accept-or-retry edge.

**Screenshot:** draw the graph — don't screenshot it. A row of six boxes with a return
arrow reads far better than code. If you want a code inset, use
`integrated-backend/learnmate/chat_agent/graph.py`, cropped to the node and edge
definitions only.
**Live shot:** the chat page mid-answer, with the streaming/progress state visible.

---

## 15 — Resource 1: Summary

**Title:** Summary

**Lead line:** One block of connected prose that says what the passage says.

**What you get**
- Written as connected prose, not a summary chopped into bullets
- Built only from the retrieved source text
- Scoped to one passage, or pooled across the whole document

**How it is checked**
- Gate 1 rejects an empty or too-thin summary without spending a judge call
- Gate 2 grades it against the source passage on the summary rubric
- Below 70, one regeneration with the judge's instruction; the better attempt wins

**Bottom box — two scopes:** *Passage* — one extract, optionally the pages that best match a topic you name. *Whole document* — read in groups and pooled, so the result covers the file rather than its first few pages. Generation runs in the background either way, with live progress on the Resources page.

**Screenshot:** a generated summary open at `/resources` → the resource view, with its
**Accepted** badge and score visible.

---

## 16 — Resource 2: Key points

**Title:** Key points

**Lead line:** The points the passage itself treats as important — which is not the same thing as a summary in bullet form.

**What you get**
- Each point a complete statement that stands on its own
- Ordered as the passage presents them
- Sized to the passage, not padded out to a round number

**How it is checked**
- Gate 1 checks count, emptiness and duplication — all decidable without a model
- Gate 2 asks what a validator cannot: is each point actually in the source, and are the important ones there
- One regeneration on a rejection

**Bottom box:** A summary compresses; key points select. Generating one from the other produces material that reads perfectly well and teaches badly — which is why they are separate tasks with separate rubrics rather than two renderings of one output.

**Screenshot:** a generated key-points resource open in the resource view. Put it beside
the summary screenshot from slide 15 if you want the contrast to land.

---

## 17 — Resource 3: MCQ

**Title:** Multiple-choice questions

**Lead line:** Four options, one right, three plausible — and the set as a whole has to be unguessable.

**What you get**
- Exactly one option marked correct
- Distractors that are plausible rather than filler
- Emitted as JSON under a grammar constraint, so it parses every time

**Gate 1 — per question**
- Four options, none blank, none duplicated
- The marked answer must be one of them
- No "all of the above" giveaway

**Gate 1 — per set**
- The answer is not always in the same slot
- The correct option is not always the longest
- The same question is not asked twice

**Bottom box — the set-level rules are the interesting ones:** Every question can be individually perfect while the set as a whole is still guessable without reading the passage, and no single-item check can see that. The bias rules only apply from four questions upward — below that, the answer landing in the same slot each time is coincidence, not a signal.

**Screenshot:** the **MCQ quiz page** (`/resources` → an MCQ → `McqQuiz`), ideally showing
a question answered with the correct/incorrect state visible. This is the most
demo-friendly screen in the app.

---

## 18 — Resource 4: Practice questions

**Title:** Practice questions

**Lead line:** Short-answer questions with reference answers — the format that makes you produce the idea instead of recognising it.

**What you get**
- Answerable from the passage alone
- A reference answer supplied with every question
- Rendered to plain text for the judge to grade

**How it is checked**
- Gate 1: question and answer both present, no duplicates — and an answer that merely restates its question is rejected
- Gate 2 grades the pair against the source: is this really the answer, and is it really supported by the passage

**Bottom box:** MCQs test recognition; short answers test recall. Keeping both is the reason there are four resource types rather than two — and adding a fifth means one module beside the existing four, one line in the task registry, one structural validator and one rubric.

**Screenshot:** the **Practice questions page** (`PracticeQuestions.jsx`), with one answer
revealed so both the question and its reference answer are on screen.

---

## 19 — User analytics

**Title:** What you did, and how well it scored

**Lead line:** Two halves, and the second is the one worth reading.

**Half one — activity**
- Documents, conversations, messages and questions asked
- Study activity over the last seven days
- Resources generated, broken down by type

**Half two — quality, from the evaluation log**
- Per task: n, min, median, max, mean, distinct and pass rate
- Acceptance rate against the judge threshold of 70
- `distinct` is the one that says whether the judge can separate good from bad at all — scores clustered in a narrow band cannot, at any threshold

**Which gate decided each attempt**

| stage | meaning |
|---|---|
| `parse` | the output could not be read as JSON at all |
| `validator` | structural checks rejected it before the judge ran |
| `judge` | the model scored it |
| `skipped` | evaluation was switched off |

**Bottom box — the distinction a pass rate hides:** A `validator` count that dominates means the generation prompt needs work, not that the threshold is too high. And acceptance rate is `null` rather than `0` when nothing has been generated — "no data" and "nothing passed" are different, and rounding the first to the second is a lie.

**Screenshot:** `http://localhost:5173/analytics`, full window, with the seven-day activity
chart populated. Generate a few resources on different days beforehand, or the chart is a
flat line and undersells the slide.

---

## 20 — UI / UX

**Title:** One blue, used sparingly

**Lead line:** A royal-blue LMS: a pale lavender rail against near-white content, and generously rounded white cards with hairline borders instead of heavy shadows.

**Palette:** `#2340E0` primary · `#E5E9FE` primary-light · `#101533` heading · `#3B4166` body · `#6C7191` muted · `#E7E9F5` border

**The rules the design system enforces**
- **One saturated colour.** `#2340E0` marks the active nav pill, the primary button and the data marks. Nothing else gets it, so the places it appears are the places that matter.
- **Status colours are reserved.** Green, amber and red mean success, warning and danger — never decoration.
- **Radii from 8 to 24 px.** Softer, larger corners are most of the difference between this and a bootstrap page.
- **Dark mode is a token swap.** Not one component is theme-aware: `bg-surface` is still `bg-surface`, and paints a different colour because the variable underneath holds one. A new screen costs nothing to support.
- **Navy-tinted greys in the dark theme.** A neutral-grey dark mode reads as a different product wearing the same logo.

**Bottom box — three kinds of route:** open (`/login`, `/register`) · explore (`/`, `/about`, `/tour` — public header when signed out, app rail when signed in) · protected (everything else). The root is Home rather than a redirect to the dashboard, because a first-time visitor landing on a login form has been asked to commit before being told what to.

**Screenshot:** the **same page in light and dark mode, side by side** — dashboard or
documents works well. That one pair proves the token-swap claim instantly.
**Optional:** a strip of the six palette swatches with their hex values.

---

## 21 — Usability

**Title:** Nothing blocks, and nothing pretends

Six boxes:

- **Slow work never blocks.** Upload, generation and chat return immediately and report progress. Leave the page, come back tomorrow — the job lives in the database, not in a browser tab.
- **Status is visible.** A document row says Processing and becomes Ready on its own. The page watches it, so there is nothing to refresh and nothing to guess at.
- **Answers arrive when readable.** A reply is handed over the moment it is finished, not when the judge is done with it — and a retry never overwrites a finished paragraph on screen.
- **One place for a dead session.** A single axios interceptor catches a 401, clears the session and redirects to login — instead of forty call sites each getting it slightly wrong.
- **Explore before committing.** Home, About and Take a Tour are readable without an account, so a visitor can find out what the product does before being asked to sign up.
- **Failures are locatable.** `/api/health` reports both databases and both model files separately, so a problem is found in seconds rather than guessed at.

**Screenshot:** the **Resources page with a job running** — the live progress bar with
something still generating above the finished items. It demonstrates three of the six
points at once.
**Second option:** `/api/health` JSON, if you didn't already use it on slide 7.

---

## 22 — Security with Keycloak

**Title:** Keycloak issues the tokens; this backend only verifies them

**Lead line:** Authentication and authorisation are separate questions, and each is asked in exactly one place.

**Flow:** `Sign in (LearnMate login theme)` → `Keycloak 26, learnmate realm, :8081` → `RS256 token signed with Keycloak's private key` → `JWKS verify — public keys, fetched once and cached` → `get_current_user on every protected route`

**Two kinds of token, one dependency.** A token this server issued is HS256, signed with a secret only it holds. A Keycloak token is RS256 and can only be checked against Keycloak's published public keys. One pair of `except` clauses catches both — and being unable to *reach* Keycloak is handled as a different thing from a bad token.

**Ownership is checked before work is queued.** `services/ownership.py` is the only place that decision is made, so there is no route that forgot to ask. Posting into somebody else's session is a 403 immediately, rather than a background job that fails a minute later.

**Bottom box — the rest of the surface:** `JWT_SECRET_KEY` is the one setting with no default, deliberately: a fallback secret works in development, ships unnoticed, and makes every token it ever signed forgeable. Passwords on the local path are bcrypt-hashed, never stored or logged in readable form. Keycloak runs `start-dev` here — the right trade for a development identity provider and the wrong one for anything reachable from outside this machine.

**Screenshot:** two images —
**(a)** the **Keycloak login page wearing the LearnMate theme** (the custom theme in
`integrated-backend/keycloak/themes/learnmate/` — this is your own work, show it), and
**(b)** the **Keycloak admin console** at `http://localhost:8081` → the `learnmate` realm,
either the Clients list or the Users list.
**Optional third:** a decoded JWT on jwt.io showing the `iss`, `exp` and `sub` claims —
use a throwaway dev token, not a real one.

---

## 23 — What next: testing and deployment

**Title:** Testing and deployment

**Testing — what already runs**
- `scripts/smoke_test.py` drives the whole system end to end — register, upload, generate, chat, analytics — with a pass or fail line per step
- `/api/health` checks both databases and both model files separately
- Every generation is validated and judged, and every verdict is logged — a continuous quality record

**Testing — what it needs**
- Unit tests over the engine: cleaning, chunking, the MCQ set-level rules
- A pytest suite in CI on every pull request
- Judge-score regression tracking, so a prompt change that quietly lowers quality is visible before it ships
- A load test on the job queue with concurrent students

**Deployment, in order of effect**
- **GPU offload first.** `LEARNMATE_N_GPU_LAYERS=-1` on a Metal or CUDA build, with `API_WARM_MODELS=1` so both models load at boot rather than inside the first question. This is the line that turns tens of seconds into seconds.
- **Keycloak from `start-dev` to `start`,** with TLS and a real database behind it.
- **Containerise the API** alongside Mongo and Qdrant, with backups on the named volumes — Mongo is the only one that is not rebuildable.
- **Promote a fine-tune when it earns it.** The moment a candidate passes document-held-out, pointing the app at it is two lines of `.env`.

**Bottom box:** None of this requires rewriting the application. The seams it was built around — the job queue, the model-backend interface, the single ownership check — are the same seams every one of these steps uses.

**Screenshot:** the terminal output of `python scripts/smoke_test.py`, showing the
pass lines for each step. Real, current, and exactly the right evidence for this slide.

---

## 24 — Closing (optional)

**Title:** Thank you — Questions

**Recap strip:** Grounded chat that cites its pages · Four resource types, each with its own structural gate · A judge that can say no, and one retry when it does · Entirely local: two 3B models, no network

**Screenshot:** none.

---

## Screenshot checklist

Take these in one sitting with the app populated:

| # | Slide | Shot |
|---|---|---|
| 1 | About | Home page `/` |
| 2 | Architecture | `docker compose ps` (+ export `docs/component-2.drawio`) |
| 3 | Preprocessing | Qdrant dashboard `:6335/dashboard`, points view |
| 4 | Generator | `/api/health` JSON |
| 5 | Judge | Compass → `evaluations`, one document expanded |
| 6 | Retrieval | Chat answer with page citations |
| 7 | Databases | Compass → all ten collections with counts |
| 8 | ML | `version_registry.csv` + the Colab run |
| 9 | Dashboard | `/dashboard` with real data |
| 10 | Upload | `/documents` upload panel **and** the Processing/Ready list |
| 11 | Chat agent | Chat mid-answer, streaming state |
| 12 | Summary | Resource view, summary, Accepted badge |
| 13 | Key points | Resource view, key points |
| 14 | MCQ | MCQ quiz page, a question answered |
| 15 | Practice | Practice questions, one answer revealed |
| 16 | Analytics | `/analytics` with the 7-day chart populated |
| 17 | UI/UX | One page in light **and** dark mode |
| 18 | Usability | Resources page with a job running |
| 19 | Security | Keycloak themed login **and** admin console realm |
| 20 | What next | `smoke_test.py` terminal output |

**Capture tips:** browser at 100% zoom, window around 1600×1000, hide bookmarks and
extensions, use a clean profile or incognito. Crop the browser chrome out unless the URL
is the point — for `/api/health` and the Keycloak console, the URL bar is worth keeping.
