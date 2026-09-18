# Test plan — LearnMateAI (live product)

**Branch:** `testing` (created from `main` at the commit this folder was added; merged
forward to current `origin/main` + `thevindu-feature` on 2026-09-18 — see RESULTS.md).  
**In scope:** `integrated-frontend/`, `integrated-backend/`.  
**Out of scope:** `model-Thevindu/` (offline LoRA eval has its own gate), root `frontend/`, `backend/`, `components-Dinura/`, deployment branches (`origin/deployment` and friends — see §9).

---

## 1. Objectives

1. Prove **auth, validation, evaluator gates, retrieval-mode routing, and HTTP error mapping** without loading GGUFs.
2. Prove **API contracts** (register/login/me, 401/400/409, 202 job shape) with mocked storage.
3. Give evaluators a **UAT script** a student can walk on a running machine.
4. Record **known product gaps** so a failing UI check is not treated as a missing backend.

---

## 2. Test strategy (three layers)

```
                 ┌─────────────────────────┐
                 │  UAT (running system)   │  student journeys, ports 5173/8010
                 └────────────▲────────────┘
                              │
                 ┌────────────┴────────────┐
                 │  Integration (TestClient)│  FastAPI routers, mocked Mongo/jobs
                 └────────────▲────────────┘
                              │
                 ┌────────────┴────────────┐
                 │  Unit (pure Python/JS)  │  security, schemas, gates, chunking
                 └─────────────────────────┘
```

| Layer | Isolated from | Must still be true |
|-------|---------------|--------------------|
| Unit | Mongo, Qdrant, llama.cpp, browser | Same functions the app imports |
| Integration | Real DB and models | Same routers and status codes |
| UAT | Nothing (optional skip) | Real 202 jobs, ingest, chat |

---

## 3. Unit test inventory

| ID | Suite | Code under test | Cases |
|----|-------|-----------------|-------|
| U-01 | Password hashing & JWT | `app/auth/security.py` | hash≠plain, verify true/false, corrupt hash→False, encode/decode, tamper, missing secret at call |
| U-02 | Password policy | `app/auth/users.py` | min length, needs a digit, 72-byte cap, empty name on register (mocked store) |
| U-03 | Request schemas | `app/schemas.py` | register/login email, generate scope regex, message length, resource types |
| U-04 | ObjectIds | `learnmate/storage/ids.py` | hex, ObjectId, junk→passthrough / None |
| U-05 | Text normalise | `learnmate/evaluator/normalise.py` | case, punctuation, whitespace |
| U-06 | MCQ gate | `learnmate/evaluator/mcq_rules.py` | 4 options, blank, duplicate, wrong key, all-of-the-above, position/length bias, duplicate stems |
| U-07 | Prose gates | `learnmate/evaluator/text_rules.py` | empty, restatement, thin summary, duplicate keypoints |
| U-08 | Chat `decide` | `learnmate/chat_agent/routing.py` | pass, budget, no critique, hopeless score, retry |
| U-09 | Resource `decide` | `learnmate/resource_agent/routing.py` | pass, budget, retry |
| U-10 | PDF validate | `learnmate/ingestion/validate.py` | not pdf, empty, oversize, ok page count |
| U-11 | Clean + chunk | `clean.py`, `chunking.py` | curly quotes, TOC skip, overlap metadata |
| U-12 | Email + tasks | `users.normalise_email`, `get_task` | case fold, unknown task |
| U-13 | Header-safe filename | `app/routers/documents.py` | quotes/newlines stripped |
| U-14 | Frontend contracts | `client.js`, `App.jsx`, `auth.js`, `DocumentsCard.jsx` | errorMessage branches, routes, API paths, multi-format accept list |
| U-15 | Error handlers | `app/errors.py` | 400/403/404/503/500 mapping |
| U-16 | Chat rename service | `app/services/chat.py::rename_session` | whitespace-only title rejected, strip + truncate, storage-miss propagates |
| U-17 | Model registry | `learnmate/llm/catalog.py` | tiny-YAML parsing, real-file load, **failed-gate model can never become `selectable_default`**, no filesystem paths in `public_models()` |
| U-18 | Resource export | `app/services/export.py` | docx/pptx bytes for summary (narrative/structured), MCQ, keypoints; format validation |
| U-19 | Hybrid retrieve merge | `learnmate/chat_agent/retrieve.py::_merge_hybrid` | ANN/BM25 dedup by chunk key, `"both"` tagging, `BM25_ANN_KEEP` cap |
| U-20 | MCQ difficulty | `learnmate/resource_agent/mcq.py::resolve_difficulty` | known tiers pass through, unknown/blank defaults to medium |

---

## 4. Integration test inventory

| ID | Suite | What is wired | Cases |
|----|-------|---------------|-------|
| I-01 | Auth API | `app/routers/auth.py` + TestClient | 201 register, 400 weak password, 409 duplicate, 401 login, `/me` with token, `/me` without |
| I-02 | Protected documents | documents router + mocked service | 401 no token, 202 upload shape, 400 bad PDF |
| I-03 | Jobs contract | jobs router | 401, 404 missing job |
| I-04 | Chat/resources 401 | chat + resources routers | unauthenticated POST rejected |
| I-05 | CORS / root | slim app | `FRONTEND_ORIGIN` reflected, `GET /` points at health |
| I-06 | Models API | `app/routers/models.py` + TestClient | 401, 200 catalog shape, no filesystem paths over HTTP |
| I-07 | Chat session rename/list | chat router + mocked service | 401, 422 (blank), 200 rename, 400 (service rejects), 401/200 list |
| I-08 | Resource export API | resources router + mocked export service | 401, 422 (bad `format` query), 200 with `Content-Disposition`, 404 (not owned), 400 |
| I-09 | Document reopen | documents router + mocked service | 401/404/200 metadata, 401/200 file stream (header-injection-safe filename), 401/200/422 pages |

---

## 5. UAT inventory

| ID | Journey | Pass if |
|----|---------|---------|
| A-01 | Public explore | `/`, `/about`, `/tour` work signed out |
| A-02 | Register + login | JWT stored; dashboard loads |
| A-03 | Upload PDF | 202, Processing → Ready (or honest error for scan) |
| A-04 | Generate keypoints | progress text changes; resource opens |
| A-05 | Chat in-document | answer cites the PDF; backend `mode` is `pdf` |
| A-06 | Chat off-document | general mode; no invented statute numbers required |
| A-07 | Reject non-PDF / huge file | client message before upload |
| A-08 | Session expiry | 401 clears storage (known: login 401 also wipes) |
| A-09 | Health | `GET http://localhost:8010/api/health` |
| A-10 | Gaps called out | no mode badge; resource scores may be hidden |

Live HTTP tests under `uat/` skip unless `LEARNMATE_UAT=1`.

---

## 6. Non-goals (do not fail the suite for these)

- Loading Qwen/Llama GGUFs in CI.
- Promoting `qwen25-lora-*`.
- OCR of scanned PDFs.
- Pixel-perfect React snapshots.

---

## 7. Entry / exit

**Entry:** `testing` branch exists; backend importable; pytest installed.  
**Exit:** `pytest testing/unit testing/integration` green; UAT checklist filled or skipped with reason; `RESULTS.md` updated.

---

## 8. Risks

| Risk | Mitigation |
|------|------------|
| Importing `learnmate.resource_agent` pulls LangGraph | Accept; do not load GGUF |
| Full `server:app` lifespan needs Mongo | Integration uses a **slim app** without lifespan |
| Smoke script default port 8000 | UAT uses **8010** |
| Empty `JWT_SECRET_KEY` | `conftest.py` sets a test secret if unset |

---

## 9. The second suite: `integrated-backend/tests/`

A separate pytest folder exists alongside this one, added directly on `main` by the
feature-adders work (office ingestion, chat sessions, latency/quality). It is **not**
under `testing/pytest.ini` (`testpaths = testing`), has no conftest of its own, and
imports the real `learnmate`/`app` packages directly rather than through this folder's
stub trick — still no Mongo/Qdrant/GGUF, just a different isolation style. Run it
separately, from `integrated-backend/`:

```bash
cd integrated-backend && python -m pytest tests -q
```

| File | Covers |
|------|--------|
| `test_office_extract.py` | `detect_kind`, legacy `.doc`/`.ppt` refusal, docx/pptx/tex extraction, `validate_upload` |
| `test_chat_sessions.py` | `preview_message`, `RenameSessionRequest` schema |
| `test_latency_quality.py` | stage timings, job deadline, resource/chat best-attempt persist, BM25 cache, `error_code` mapping, chat rewrite heuristic |

The two suites overlap deliberately at the schema/contract level (e.g. both touch
`RenameSessionRequest`) but test different layers — this folder adds the HTTP and
service-mocked coverage `integrated-backend/tests/` does not have. Consider folding
`integrated-backend/tests/` into this folder's `pytest.ini` `testpaths` in a future pass
so one command runs everything; not done here to avoid changing files outside `testing/`
without the team's sign-off (see PROCESS.md §0).

## 10. Known gaps (not attempted here)

- **Gate 2 judge behaviour** for the MCQ distractor checker and summary-style rubric
  lines needs a live judge GGUF — out of scope for this pytest gate by design (§6).
- **No frontend component test runner.** `integrated-frontend/package.json` has no
  `test` script and no Vitest/Jest/Testing Library. `test_frontend_contracts.py` (U-14)
  greps compiled source text; it does not render `DocumentReader.jsx`, `Flashcards.jsx`,
  `WorkspaceChat.jsx`, or `CitationChips.jsx`, all added since the last full pass.
- **Live UAT** (A-01…A-10, plus the new document-reader/rename/reopen journeys) was not
  run — no Docker/Mongo/Qdrant/GGUF stack in this environment. See PROCESS.md §1 step 4.
- **Deployment/CI configuration** on `origin/deployment`, `origin/dinura-deployment`,
  `origin/dinura-feedback-deploy` (Docker Compose, Nginx, AWS SSM `deploy.yml`) has no
  automated test anywhere in the repository, on any branch.
- **Multi-model switching** (`GET /api/models` is covered; actually loading/unloading a
  second GGUF on `model_id` is not — needs the live stack).
- **BM25 in production**: `_merge_hybrid` is unit-tested (U-19); whether BM25-only chunks
  ever survive the reranker in practice (`retrieval_mix.rerank_kept`) is a live-system
  question the code docstrings themselves say has not been measured yet.
