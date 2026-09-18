# Master Test Report — LearnMateAI

**Version 2.0 — 2026-09-18**
**Author:** Thevindu Fernando (`thevindu-feature`)
**Supersedes:** `testing/RESULTS.md` run of 2026-08-19 (97 passed)

This report consolidates the project's existing test plan (`testing/PLAN.md`,
`testing/PROCESS.md`, `testing/RESULTS.md` on the `testing` branch) with a pass done on
2026-09-18: the test suite was brought forward to cover everything merged into `main`
plus this branch's own unmerged work, gaps were filled with 51 new tests, and every
other branch on `origin` was surveyed for untested functionality. It does not replace
the `testing` branch's own documents — it points at them and adds what they did not yet
cover.

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
   available in this environment — see §8).
2. **Find what is untested**, both within `integrated-backend`/`integrated-frontend` and
   across every other branch on `origin`, so a reviewer knows the difference between
   "not tested because it doesn't need to be" and "not tested because nobody has gotten
   to it yet."
3. **Leave the record in a state the team can act on** — updated `testing/PLAN.md` /
   `RESULTS.md`, and this report, rather than a one-off pass that goes stale again.

---

## 2. Target test items

| Area | What it is | In scope this pass |
|---|---|---|
| `integrated-backend/app` | FastAPI routers, auth, schemas, error mapping | Yes |
| `integrated-backend/learnmate` | Ingestion, chat agent, resource agent, evaluator gates, retrieval, storage | Yes (unit-level; the LLM judge and generator themselves are not) |
| `integrated-backend/tests/` | A second, separate pytest suite added by the feature-adders work | Yes (run, not restructured) |
| `integrated-frontend/src` | React app — API clients, routes, and one component (`DocumentsCard.jsx`) checked by source-text assertions | Partial — no component render/unit tests exist (§8) |
| `testing/uat/` | Scripted student journeys against a running stack | Checklist reviewed; live run not attempted (§8) |
| `model-Thevindu/` | Offline LoRA fine-tuning track | Out of scope — has its own gate (`acceptance_thresholds.yaml`); the one candidate so far (`qwen25-lora-20260815-090709`) already failed it and stays `experimental: true` |
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
§8 for why, and what that means for `DocumentReader.jsx`, `Flashcards.jsx`,
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
| `thevindu-models` (local) | 8 ahead, 38 behind | A model-comparison harness under `thevindu-models/`, `models_registry.yaml` entries | **Yes** — `test_comparison_registry.py` | Predates `main`'s multi-format ingestion; would need a rebase before merging, or it regresses office-document upload |
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

## 8. Known gaps and residual risk

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

None of these are regressions from this pass — they are the honest boundary of what
unit/integration testing without a live stack can prove, stated so the next person
doesn't mistake "148 unit/integration tests pass" for "the product works end to end."

---

## 9. References

- `testing/PLAN.md`, `testing/PROCESS.md`, `testing/RESULTS.md`, `testing/README.md` —
  branch `testing`
- [docs/feature-adders/CHANGELOG.md](feature-adders/CHANGELOG.md),
  [PLAN.md](feature-adders/PLAN.md),
  [LATENCY_QUALITY_FAILURES.md](feature-adders/LATENCY_QUALITY_FAILURES.md) — branch
  `thevindu-feature`
- `model-Thevindu/03_testing_and_versioning/acceptance_thresholds.yaml`,
  `model-Thevindu/04_docs/model_card.md` — the offline ML track's own gate (out of scope
  here, referenced for the failed-gate/`selectable_default` safety property in §3.1)
- pytest 8+, FastAPI `TestClient`, `unittest.mock` — the testing stack itself; see
  `testing/requirements.txt`
