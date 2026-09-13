# Test plan — LearnMateAI (live product)

**Branch:** `testing` (created from `main` at the commit this folder was added).  
**In scope:** `integrated-frontend/`, `integrated-backend/`.  
**Out of scope:** `model-Thevindu/` (offline LoRA eval has its own gate), root `frontend/`, `backend/`, `components-Dinura/`.

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
| U-14 | Frontend contracts | `client.js`, `App.jsx`, `auth.js` | errorMessage branches, routes, API paths |
| U-15 | Error handlers | `app/errors.py` | 400/403/404/503/500 mapping |

---

## 4. Integration test inventory

| ID | Suite | What is wired | Cases |
|----|-------|---------------|-------|
| I-01 | Auth API | `app/routers/auth.py` + TestClient | 201 register, 400 weak password, 409 duplicate, 401 login, `/me` with token, `/me` without |
| I-02 | Protected documents | documents router + mocked service | 401 no token, 202 upload shape, 400 bad PDF |
| I-03 | Jobs contract | jobs router | 401, 404 missing job |
| I-04 | Chat/resources 401 | chat + resources routers | unauthenticated POST rejected |
| I-05 | CORS / root | slim app | `FRONTEND_ORIGIN` reflected, `GET /` points at health |

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
