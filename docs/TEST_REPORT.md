# Master Test Report — LearnMateAI

**Version 2.1 — 2026-09-20**
**Author:** Thevindu Fernando (`thevindu-feature`)
**Supersedes:** `testing/RESULTS.md` run of 2026-08-19 (97 passed)

This report consolidates the project's existing test plan (`testing/PLAN.md`,
`testing/PROCESS.md`, `testing/RESULTS.md` on the `testing` branch) with a pass done on
2026-09-18: the test suite was brought forward to cover everything merged into `main`
plus this branch's own unmerged work, gaps were filled with 51 new tests, and every
other branch on `origin` was surveyed for untested functionality. It does not replace
the `testing` branch's own documents — it points at them and adds what they did not yet
cover.

**2026-09-20 addition:** §8 adds the `thevindu-models` branch's laptop model-comparison
work — three live roles (generator, judge, embeddings), each benchmarked against two
off-the-shelf alternatives, with the resulting keep/promote decisions and why. Every
number quoted there was independently re-read from that branch's raw result files for
this report, not copied from its summary on faith.

---

## 1. Evaluation mission and test motivation

LearnMateAI is an AI-powered study platform for Sri Lankan legal education: a student
uploads a source document (PDF, Word, PowerPoint, or LaTeX), asks grounded questions
about it, and generates study resources (MCQs, summaries, key points, practice
questions) that a second model — the judge — grades before the student ever sees them.
The live path is `integrated-frontend` (React/Vite) + `integrated-backend`
(FastAPI + MongoDB + Qdrant + local Qwen 2.5 / Llama 3.2 GGUF models via llama.cpp).

Since the last recorded test run (2026-08-19, 97 tests), a large amount of work has
landed without a corresponding test pass:

- On `main`: multi-format ingestion (Word/PowerPoint/LaTeX), BM25 hybrid retrieval,
  multi-model switching, summary style and MCQ difficulty controls, a Word/PowerPoint
  export endpoint, and a UI refresh — all documented in
  [docs/feature-adders/CHANGELOG.md](feature-adders/CHANGELOG.md) and
  [docs/feature-adders/LATENCY_QUALITY_FAILURES.md](feature-adders/LATENCY_QUALITY_FAILURES.md).
- On `thevindu-feature` (unmerged): chat rename/resume, a full-window PDF/text reader,
  and reopening past uploads at `/documents/:id`.

The mission of this pass was threefold:

1. **Prove the merged and unmerged feature surface still behaves correctly** — not just
   that the original 97 tests still pass, but that the large amount of new code has real
   coverage, at the unit/integration level (no live Docker/Mongo/Qdrant/GGUF stack was
   available in this environment — see §9).
2. **Find what is untested**, both within `integrated-backend`/`integrated-frontend` and
   across every other branch on `origin`, so a reviewer knows the difference between
   "not tested because it doesn't need to be" and "not tested because nobody has gotten
   to it yet."
3. **Leave the record in a state the team can act on** — updated `testing/PLAN.md` /
   `RESULTS.md`, and this report, rather than a one-off pass that goes stale again.
4. **Verify, not transcribe, the model-selection work on `thevindu-models`** (§8) — the
   branch already ran its own comparisons; this pass's job was to check its safety test
   still passes and that its headline numbers match its own raw result files before
   repeating them here.

---

## 2. Target test items

| Area | What it is | In scope this pass |
|---|---|---|
| `integrated-backend/app` | FastAPI routers, auth, schemas, error mapping | Yes |
| `integrated-backend/learnmate` | Ingestion, chat agent, resource agent, evaluator gates, retrieval, storage | Yes (unit-level; the LLM judge and generator themselves are not) |
| `integrated-backend/tests/` | A second, separate pytest suite added by the feature-adders work | Yes (run, not restructured) |
| `integrated-frontend/src` | React app — API clients, routes, and one component (`DocumentsCard.jsx`) checked by source-text assertions | Partial — no component render/unit tests exist (§9) |
| `testing/uat/` | Scripted student journeys against a running stack | Checklist reviewed; live run not attempted (§9) |
| `model-Thevindu/` | Offline LoRA fine-tuning track | Out of scope — has its own gate (`acceptance_thresholds.yaml`); the one candidate so far (`qwen25-lora-20260815-090709`) already failed it and stays `experimental: true` |
| `thevindu-models/` (local branch) | Laptop drop-in comparisons for generator/judge/embeddings/reranker | Reviewed in depth (§8) — its own safety test re-run and its raw results independently checked; not merged, not part of the 177-test combined total |
| Root `frontend/`, `backend/`, `components-Dinura/` | Stale/superseded folders | Out of scope |
| Deployment branches (`origin/deployment` and related) | Docker, Nginx, AWS SSM deploy pipeline | Surveyed, not tested — no automated tests exist for this anywhere (§7) |

---

## 3. Test approach

Three layers, unchanged from `testing/PLAN.md`'s original design and still the right
shape for this stack:

```
UAT (running system, ports 5173/8010/27018/6335)
        ↑
Integration (FastAPI TestClient, routers + auth + error mapping, storage mocked)
        ↑
Unit (pure Python — security, schemas, evaluator gates, ingestion, export, catalog)
```

Backend unit and integration tests stub `learnmate`'s heavier sub-packages
(`chat_agent`, `resource_agent`) at the module level (see `testing/conftest.py`) so
importing a router never triggers a GGUF load, a LangGraph build, or a Mongo/Qdrant
connection. A second, independently-written suite (`integrated-backend/tests/`) takes
the opposite approach — real imports, no stub — and is still light enough to run in
~30 seconds because the modules it imports (`persist`, `bm25`, `runtime_limits`,
`worker`) don't reach the model layer either. Both are legitimate and are documented
together rather than merged into one, to avoid restructuring code outside this branch's
remit.

### 3.1 Data and integrity testing

MongoDB access goes through thin storage modules (`learnmate/storage/*`) that every
service function calls by name, which is what makes them mockable with
`unittest.mock.patch` rather than a real database or `mongomock`. Ownership integrity
(a user can only reach their own documents/sessions/resources) is enforced in
`app/services/ownership.py` (`require_session`, `require_resource`, `require_document`)
and is exercised through the HTTP layer in the integration suite (401 unauthenticated,
403 wrong owner via `AccessDenied`, 404 missing via `NotFound` — `app/errors.py`, U-15).
The model registry (`learnmate/models_registry.yaml`) has its own data-integrity rule —
a failed-gate model can never present itself as the selectable default — verified
end-to-end against the real parser in `test_models_registry.py` (U-17), including a
version that writes a rogue registry file to a temp path and loads it for real rather
than re-implementing the safety check in the test.

### 3.2 Function testing

The bulk of the suite: pure-function and mocked-service tests against
`app/services/*`, `app/schemas.py`, and `learnmate/*`. New this pass: chat session
rename (U-16), resource export to docx/pptx for every task type (U-18), the BM25/ANN
hybrid merge (U-19), and MCQ difficulty tier resolution (U-20). See
`testing/PLAN.md` §3 for the full numbered inventory (U-01…U-20) and §4 for the HTTP
contract inventory (I-01…I-09).

### 3.3 User interface testing

Limited to what can be checked without a browser: `testing/unit/test_frontend_contracts.py`
(U-14) greps the compiled React source for the API paths, error-handling branches, and
routes the app is supposed to have, and was extended this pass to check the multi-format
upload accept list. **This is a source-text check, not a rendered-component test** — see
§9 for why, and what that means for `DocumentReader.jsx`, `Flashcards.jsx`,
`WorkspaceChat.jsx`, and `CitationChips.jsx`, all added since the last pass and currently
covered only indirectly, through the backend endpoints they call.

### 3.4 Performance profiling and load testing

Not executed this pass (needs the live stack). The project's own analysis in
[LATENCY_QUALITY_FAILURES.md](feature-adders/LATENCY_QUALITY_FAILURES.md) is the
authoritative source: documented ~30–60s per chat turn locally (dominated by the ~25–36s
judge call), a bottleneck map, and the reasoning for why naive fixes (more retries, a
stricter Gate 2, switching models per request) make it worse, not better. Phase 2 of
that work added the instrumentation (`rewrite_ms`, `retrieve_ms`, `generate_ms`,
`judge_ms`, `model_load_ms` on every job result) needed to replace those estimates with
real numbers — unit-tested here (`TimingTests` in `integrated-backend/tests/test_latency_quality.py`)
but not yet exercised against a running system to produce a first real measurement.

### 3.5 Security and access control testing

Covered at the levels that don't need a live network:

- **Authentication**: password hashing/verification, JWT encode/decode/tamper
  detection, missing-secret handling (U-01); every protected endpoint checked for a
  401 without a token (U-14 route list, I-01 through I-09 individually).
- **Authorization**: ownership checks return 403/404 rather than leaking another
  user's data (`app/errors.py` mapping, U-15; exercised per-resource in I-07/I-08/I-09).
- **Header injection**: `_safe_filename` strips quotes/CR/LF before they reach a
  `Content-Disposition` header (U-13, plus the new I-09 test that sends a filename
  containing `\r\n` and an injected header line through the real endpoint and asserts
  the response header stays on one line).
- **Registry integrity**: the failed-gate-model safety rule (§3.1 / U-17) is a security
  property as much as a data one — it is what stops an ML candidate that failed
  accuracy/latency/hallucination gates from silently becoming what every student talks
  to.
- **Not covered**: no dependency/SAST scan was run as part of this pass; no live
  penetration test. SQL injection is structurally out of scope (MongoDB via `pymongo`,
  no raw query strings built from user input in the code paths reviewed).

### 3.6 Failover and recovery testing

`StorageUnavailable` (Mongo down) and `QdrantUnavailable` (vector store down) map to 503
via registered exception handlers, unit-tested in the error-mapping suite (U-15) and in
`ErrorCodeTests` (`integrated-backend/tests/test_latency_quality.py`), which also checks
that a job-level `error_code` (`storage`/`model`/`parse`/`timeout`/`interrupted`/`unknown`)
is derivable from the underlying exception. `LEARNMATE_JOB_TIMEOUT_S` (default `0`,
off) and the deadline-checking helper are unit-tested (`DeadlineTests`). **Not
tested**: an actual failover — killing Mongo or Qdrant mid-request and watching the
system recover — which needs the live stack and was out of scope for this pass by your
earlier decision (unit + integration only).

### 3.7 Configuration testing

The project's port convention (Vite 5173, FastAPI **8010** — not 8000, MongoDB 27018,
Qdrant 6335) and feature flags (`LEARNMATE_HYBRID_BM25`, `LEARNMATE_JOB_TIMEOUT_S`,
`KEYCLOAK_ENABLED`, `LEARNMATE_GENERATOR_MODEL`) are documented in `testing/README.md`
and `docs/feature-adders/PLAN.md` but not automated — there is no test that boots the
app under each flag combination. The `conftest.py` stub sets `API_WARM_UP=0`,
`API_WARM_MODELS=0`, `KEYCLOAK_ENABLED=0` for the test environment specifically, which
is itself a configuration decision worth being aware of when reading a "green" result:
it proves the code paths work with warm-up and Keycloak off, not on.

---

## 4. What changed in this pass

### 4.1 Bringing the suite forward

The `testing` branch (last touched 2026-08-19) had fallen behind: `origin/main` had
merged 37 commits it didn't have, and this branch (`thevindu-feature`) had 3 more on top
of that `testing` had never seen. Both were merged into `testing` (clean, no conflicts —
`testing`'s own tip was already an ancestor of `main`). That surfaced one real
compatibility gap and three stale assertions:

- `testing/conftest.py` stubbed `learnmate.ingestion` without the new `validate_upload`,
  `detect_kind`, and `kind_from_record` exports that `app/services/documents.py` now
  imports — fixed by extending the stub.
- Three `testing/unit` assertions were written against the old PDF-only upload
  messages and started failing once multi-format ingestion changed those messages.
  **All three were product improvements, not regressions** — see `testing/RESULTS.md`
  for the exact before/after message text. Fixing them meant updating the assertion,
  not the product code, except for one case (`test_garbage_bytes_are_corrupt`) where a
  new test was added alongside the fix to keep covering the original code path (a
  malformed-but-`%PDF`-headed file), which the old test data no longer reached now that
  a cheaper magic-byte check runs first.

### 4.2 New coverage (51 tests, 9 files)

Full list with exact IDs in `testing/PLAN.md` §3–4 and `testing/RESULTS.md`. Summary:

| Feature (from CHANGELOG.md) | Test coverage added |
|---|---|
| Multi-model registry / `GET /api/models` | Unit: parsing, real-file load, the no-failed-gate-default rule, no leaked filesystem paths. Integration: 401/200, router wired into the test app (it wasn't before). |
| Export docx/pptx | Unit: byte generation for every resource task type (summary narrative + structured, MCQ, keypoints), format validation. Integration: 401/422/200/404/400. |
| BM25 hybrid retrieve | Unit: the merge/dedup function directly (`_merge_hybrid`) — ANN+BM25 dedup by chunk key, `"both"` tagging, the `BM25_ANN_KEEP` cap. |
| Chat rename/resume | Unit: the service-level whitespace-title rejection the schema alone doesn't catch. Integration: rename and list endpoints, 401/422/200/400. |
| Full-window reader / past uploads reopen | Integration: `GET /api/documents/{id}`, `/file`, `/pages` — metadata, byte streaming with header-injection-safe filenames, page-range validation. These three endpoints had **zero** integration coverage before this pass despite backing two shipped features. |
| MCQ difficulty | Unit: tier resolution and its default-to-medium fallback. |
| Summary style / difficulty request validation | Unit: `GenerateRequest.summary_style` / `.difficulty` pattern enforcement. |

### 4.3 Results

| Suite | Command | Passed | Failed | Skipped |
|---|---|---:|---:|---:|
| `testing/unit` + `testing/integration` | `pytest testing/unit testing/integration -q` | 148 | 0 | — |
| `testing/uat` | `pytest testing/uat -q` | — | 0 | 4 (no live stack) |
| `integrated-backend/tests` | `pytest tests -q` (from `integrated-backend/`) | 29 | 0 | 0 |
| **Combined** | | **177** | **0** | **4** |

181 test items collected across both suites; 177 executed and green, 4 skipped by design
(live UAT, no stack available). Up from 97 passed / 4 skipped on 2026-08-19.

---

## 5. Deliverables

| Deliverable | Location | Frequency |
|---|---|---|
| Test plan (scope, layers, numbered case inventory, risks, gaps) | `testing/PLAN.md` | Updated this pass; update again whenever a feature ships without matching cases |
| Process (how to run, commit convention, isolation rules) | `testing/PROCESS.md` | Unchanged this pass |
| Last recorded run (pass/fail, what changed, why) | `testing/RESULTS.md` | Updated this pass |
| Manual UAT script | `testing/uat/UAT_CHECKLIST.md` | Reviewed, not re-run |
| This consolidated report | `docs/TEST_REPORT.md` (this file) | New |
| Branch survey (§7) | This file | New |

---

## 6. Reporting on test coverage

`testing/RESULTS.md` is updated after every full run with date, command, and
pass/fail/skip counts — this pass followed that convention. The project does not yet
have a CI job that runs `pytest testing/unit testing/integration` automatically on
every push (checked: `.github/workflows/deploy.yml` exists and handles deployment, no
`test`/`ci.yml` workflow was found on `main` or `thevindu-feature`). Adding one would
turn this from "someone remembers to update RESULTS.md" into a gate — worth raising
with the team, but out of scope for this pass (it would touch `.github/`, which affects
shared CI for everyone, not just this branch).

---

## 7. Branch survey

Per your request, every branch on `origin` was reviewed (not checked out or merged —
read via `git log`/`git diff`/`git show` against `origin/main`) for functionality that
exists nowhere else and has no test coverage.

| Branch | vs `origin/main` | Unique content | Own tests? | Note |
|---|---|---|---|---|
| `origin/dinura`, `dinura-dev`, `dinura-model-combine`, `dinura-work` | 0 ahead, 54–149 behind | None | — | Fully merged into `main` already; safe to ignore |
| `origin/copilot/fix-failing-github-actions-job` | 4 ahead, 0 behind | Whitespace + a `permissions: contents: read` line on `deploy.yml` | N/A | Trivial CI hygiene; safe to fold in or ignore |
| `thevindu-dev` (local) | 2 ahead, 66 behind | `model-Thevindu` corpus/eval-pack data and docs only | Eval scripts, no app tests | Not app code; out of scope for this report |
| `thevindu-models` (local) | 8 ahead, 38 behind | A model-comparison harness under `thevindu-models/`, `models_registry.yaml` entries | **Yes** — `test_comparison_registry.py` | Predates `main`'s multi-format ingestion; would need a rebase before merging, or it regresses office-document upload. Full comparison detail in §8. |
| `origin/dinura-final` | 1 ahead, 0 behind | `learnmate/ingestion/convert.py`, document-service tweaks, `Flashcards.jsx`/`ResourcesPanel.jsx` changes, `lib/dateTime.js` | No | Unmerged app functionality with zero test coverage — worth a look before it's lost |
| `origin/tharumini-dev` | 2 ahead, 53 behind | `Masthead.jsx` nav redesign, a Keycloak logout/dead-auth-path fix | No | Untested auth-adjacent change |
| `origin/dinura-deployment` | 11 ahead, 24 behind | First Docker/Nginx/SSH deploy stack (`docker-compose.yml`, `Dockerfile`s, `nginx/default.conf`) | No | Early experiment; superseded by the next two rows |
| `origin/dinura-feedback-deploy` | 29 ahead, 24 behind | `docker-compose.prod.yml`, TLS Nginx config, AWS SSM deploy with diagnostics; deletes the stale root `frontend/` | No | Iterates toward production readiness |
| `origin/deployment` | 35 ahead, 0 behind | The most mature deploy stack: AWS SSM `deploy.yml` with concurrency guards and health checks, `deploy-ec2.sh`, `configure-keycloak.sh`; also carries `Masthead.jsx` | No | **Strongest gap**: real production infrastructure with no automated test anywhere |

No branch on `origin` contains Kubernetes manifests. Three branches
(`dinura-deployment`, `dinura-feedback-deploy`, `deployment`) build up a Docker
Compose + Nginx + AWS SSM deployment layer that `main` does not have at all, and none
of it — on any branch — has an automated test. If a "configuration/deployment testing"
gate is wanted (§3.7), that's where it would start: `origin/deployment` is the most
current version of that work.

---

## 8. Model comparison — `thevindu-models` (choosing the best drop-in per role)

`thevindu-models` is a separate, unmerged local branch (branched from `thevindu-feature`)
that asks a narrower question than the LoRA track in `model-Thevindu/` (§3.1). That track
asks "can we train a better model" — and its one candidate failed the gate. This branch
asks instead: *for each of the live app's model-shaped roles, is there a better
**off-the-shelf, laptop-sized drop-in** than what's already running, without training
anything?*

**Verified for this report**, not transcribed from the branch's own summary: a git
worktree of `thevindu-models` was checked out separately, its safety test
(`integrated-backend/tests/test_comparison_registry.py`) was re-run and passes **3/3** —
Qwen 2.5 3B stays the sole `selectable_default`, every comparison candidate stays
`experimental: true`, and the comparison YAML's candidate counts and embedding
query/passage prefixes are exactly what the eval scripts assume. Every headline number
below was independently re-read from the branch's own raw result files
(`results/gguf.json`, `results/real_pdf.json`, `results/retrieval.json`) and matches its
`RESULTS.md` tables exactly.

### 8.1 Methodology

| | |
|---|---|
| Machine | One Windows laptop, CPU-only (AMD64, Intel Family 6 Model 186) — **not** Colab T4, **not** a uvicorn server p95 |
| Toy fixture | `fixtures/legal_retrieval.jsonl` — 36 chunks, 14 queries |
| Real fixture | `integrated-backend/data/Company-law-part1-notes.pdf` — 7 pages → 34 live-ingested chunks, 10 questions |
| Generator/judge fixtures | `fixtures/generator_prompts.jsonl`, `fixtures/judge_gold.jsonl` |
| Promotion rule | A candidate must beat the live baseline on **every** primary metric for its role, not just one — `RESEARCH.md`'s "What 'better' means" table |
| Safety rule | No candidate may carry `selectable_default: true` while `experimental: true` (same rule as the LoRA track, §3.1) — enforced by the registry parser itself, confirmed by the re-run test above |

Three model roles were compared, each against the live baseline plus two alternative
candidates from a *different* model family (never "another Qwen," so a win means an
architecture win, not a size change).

### 8.2 Generators — vs Qwen 2.5 3B Instruct (live)

| Candidate | Grounded hit rate | JSON validity | Mean ms | Verdict |
|---|---:|---:|---:|---|
| **Qwen 2.5 3B (live)** | **1.00** | **1.00** | 15,082 | baseline — kept |
| Gemma 2 2B Instruct | 0.67 | 0.00 | 14,857 | reject — fails JSON validity |
| Phi-3.5 Mini Instruct | 0.00 | 0.00 | 17,822 | reject — fails both metrics |

**Why Qwen stays:** it is the only candidate that both stayed grounded in the source
passage *and* produced schema-valid MCQ JSON on this laptop. Gemma matched Qwen's speed,
but its MCQ item failed the live "4 options, `answer` ∈ `options`" check. Phi's run
completed (not an out-of-memory skip) but decoded to garbage bytes under the app's empty
`chat_format` contract — a genuine drop-in failure, not a missing file.

### 8.3 Judges — vs Llama 3.2 3B Instruct (live)

| Candidate | Gold-label agreement | Mean ms | Verdict |
|---|---:|---:|---|
| **Llama 3.2 3B (live)** | **1.00 (5/5)** | 32,967 | baseline — kept |
| Granite 3.2 2B Instruct | 1.00 (5/5) | 36,879 | matches agreement, ~12% slower — **promotable candidate**, not promoted |
| Gemma 2 2B (judge role) | 1.00 (5/5) | 38,323 | not a drop-in — only agrees after folding the system prompt into the user turn, which the live judge node does not do |

**Why Llama stays, and why Granite is worth watching:** Granite ties Llama on the
gold-label pass/fail set without a large latency regression — under the branch's own
rule ("match or beat agreement without a large latency cost"), that clears the bar to be
a *candidate*. It has not been promoted: the branch's own four-eyes review checklist is
still unchecked, and a judge swap changes what "passed" means for every future
generation — that stays a documented option, not a flipped default, until a second
person signs off.

### 8.4 Embeddings — vs all-MiniLM-L6-v2 (live)

The most important finding in this track is that the toy fixture and a real document
**disagree**, and the branch trusted the real one over the synthetic win:

| Candidate | Toy NDCG@5 | Toy query ms | Real-PDF NDCG@5 | Real-PDF gold-in-top-3 | Real-PDF query ms |
|---|---:|---:|---:|---:|---:|
| **MiniLM-L6 (live)** | 0.9209 | 37.7 | **0.9500** | **1.00** | **33.7** |
| BGE-small-en-v1.5 | 0.9116 | 72.9 | 0.9377 | 1.00 | 63.4 |
| E5-small-v2 | **0.9379** | 196.6 | 0.9133 | 0.90 | 61.4 |

**Why MiniLM stays, despite E5 "winning" first:** on the 36-chunk toy fixture, E5's
asymmetric query/passage training gave it the best NDCG. Re-run against a real 7-page
company-law PDF, that reversed — MiniLM beat E5, and E5 missed the gold chunk in its top
3 on one question entirely. The toy fixture's ~5× query-latency gap also shrank to ~1.8×
on the real document. A model that wins on 14 synthetic queries and loses on a real one
is exactly the case a promotion gate exists to catch. Switching embedders also forces a
mandatory re-ingest of every stored PDF (vectors from different models are not
comparable) — not a decision to make from one fixture.

### 8.5 Reranker and retrieval agent (a related fourth comparison)

Run alongside the embeddings work, since both sit in the retrieve stage:

| Reranker | Toy NDCG@5 | Real-PDF NDCG@5 | Real-PDF ms/~20 pairs | Verdict |
|---|---:|---:|---:|---|
| **MiniLM-L-6 (live)** | 0.9473 | 0.992 | 1,069 | baseline — kept |
| MiniLM-L-12 | 0.9736 | 0.992 (tie) | 2,128 (2×) | reject — no real-document lift, 2× cost |
| BGE-reranker-base | 0.9473 (tie) | not re-run | 7,047 | reject — ties L-6 at ~11× the latency on the toy fixture alone |

Retrieval agent (ANN-only vs. the live hybrid ANN+BM25): tied on both fixtures, but on
the real PDF, BM25-only chunks **did** survive into the reranked top-3 once across ten
questions (26 of the kept chunks were found by both methods, 1 was BM25-only). **Hybrid
stays on** — a tie is not evidence it is a no-op, and the one case where BM25 alone
surfaced the answer is exactly what the flag exists for.

### 8.6 Decision summary

None of the eight candidates evaluated changed a live default. `.env` and
`models_registry.yaml`'s `selectable_default` were not touched — confirmed by the
registry-safety test in the intro to this section, not just asserted:

| Role | Live default | Promote now? | Why |
|---|---|---|---|
| Generator | Qwen 2.5 3B | No | No alternative beat Qwen on both grounding and JSON validity |
| Judge | Llama 3.2 3B | No | Granite is a viable candidate, but four-eyes review hasn't happened |
| Embeddings | all-MiniLM-L6-v2 | No | The toy-fixture winner (E5) lost on the real document |
| Reranker | MiniLM-L-6 | No | Larger/alternate rerankers didn't lift real-document quality |
| Retrieval agent | Hybrid ANN+BM25 | Keep as-is | Already the live default; real-PDF evidence supports keeping it on |

### 8.7 What this track does not claim

Directly from the branch's own "What we are not claiming" section, because it is the
right level of honesty for this report too: Colab T4 numbers from the LoRA eval are not
this laptop's GGUF numbers; this laptop's retrieve latency is not a uvicorn chat p95; a
36-chunk fixture does not mean retrieval is "solved"; and end-to-end chat p95 with any of
these candidates has not been measured (`end_to_end_chat_p95_ms: null` in
`results/real_pdf.json` — the live stack was down when this was run, the same constraint
as §3.4/§3.6 in this report).

### 8.8 Status

Not merged to `main`. Per the branch's own next-actions list, a second person needs to
sign off on `RESULTS.md` before anything here becomes a registry default, and the branch
predates `main`'s multi-format ingestion work — it is 38 commits behind (§7) — so it
would need a rebase before that review could even happen against current code.

---

## 9. Known gaps and residual risk

Carried forward from `testing/PLAN.md` §10, repeated here because it's the part a
reviewer is most likely to act on:

1. **No live UAT was run.** This environment has no Docker/Mongo/Qdrant/GGUF stack, and
   the decision for this pass was unit+integration only (matching how the last recorded
   run already treated UAT — skipped, not failed). The 10-item checklist
   (`testing/uat/UAT_CHECKLIST.md`) has not been walked against the new features
   (rename, reopen, reader, export, model switch) by a person or the live-HTTP script.
2. **No frontend component test runner exists.** `integrated-frontend/package.json` has
   no `test` script, no Vitest/Jest, no Testing Library. `DocumentReader.jsx`,
   `Flashcards.jsx`, `WorkspaceChat.jsx`, and `CitationChips.jsx` — all shipped since the
   last test pass — are exercised only through the backend contracts they call, never
   as rendered components. Setting one up is a real, separate piece of work (choosing
   Vitest vs. Jest, wiring it into `vite.config`, writing the first components' tests)
   and was not attempted here since it goes beyond "more tests for what's there."
3. **The Gate 2 judge is untestable without a GGUF**, by design (`PROCESS.md` §3: "Do
   not call `get_generator_llm()` / `get_judge_llm()` in this folder"). The MCQ
   distractor checker and summary-style rubric additions therefore have no automated
   coverage of whether the judge actually applies them correctly — only that the
   plumbing around them (difficulty resolution, schema validation, export formatting)
   is correct.
4. **No automated test for the deployment branches** (§7) — the most mature one
   (`origin/deployment`) is real, unmerged, production-facing infrastructure with zero
   coverage.
5. **BM25-in-production is unmeasured.** `_merge_hybrid` is unit-tested (U-19), but
   whether BM25-only chunks actually survive the reranker in real traffic
   (`retrieval_mix.rerank_kept`) is a live-system question the code's own comments say
   has not been checked yet — before promoting hybrid retrieve as "better," that number
   needs to come from a running system, not this suite.
6. **No CI gate** runs this suite automatically (§6).
7. **`thevindu-models`'s comparisons have no four-eyes review and no end-to-end chat
   p95** (§8.7–8.8). Granite-as-judge is a documented candidate, not a validated one; the
   branch is also 38 commits behind `main` and would need a rebase before it could be
   reviewed against current code.

None of these are regressions from this pass — they are the honest boundary of what
unit/integration testing without a live stack can prove, stated so the next person
doesn't mistake "148 unit/integration tests pass" for "the product works end to end."

---

## 10. References

- `testing/PLAN.md`, `testing/PROCESS.md`, `testing/RESULTS.md`, `testing/README.md` —
  branch `testing`
- [docs/feature-adders/CHANGELOG.md](feature-adders/CHANGELOG.md),
  [PLAN.md](feature-adders/PLAN.md),
  [LATENCY_QUALITY_FAILURES.md](feature-adders/LATENCY_QUALITY_FAILURES.md) — branch
  `thevindu-feature`
- `model-Thevindu/03_testing_and_versioning/acceptance_thresholds.yaml`,
  `model-Thevindu/04_docs/model_card.md` — the offline ML track's own gate (out of scope
  here, referenced for the failed-gate/`selectable_default` safety property in §3.1)
- `thevindu-models/README.md`, `RESEARCH.md`, `RESULTS.md`, `comparison_registry.yaml`,
  `results/gguf.json`, `results/real_pdf.json`, `results/retrieval.json`,
  `integrated-backend/tests/test_comparison_registry.py` — branch `thevindu-models`,
  detailed in §8
- pytest 8+, FastAPI `TestClient`, `unittest.mock` — the testing stack itself; see
  `testing/requirements.txt`
