# Testing process — full cycle

This is how LearnMateAI is tested on the **`testing`** branch. The product code stays a copy of `main`; this folder is additive.

---

## 0. Branch rule

1. `git checkout main` and update it.
2. `git checkout -b testing` (once) so `testing` starts as a copy of `main`.
3. All test commits and pushes go to **`origin/testing` only**.
4. Do not commit tests to `main` or `thevindu-dev` unless the team explicitly asks.

---

## 1. What we test, in order

### Step 1 — Plan
Read `PLAN.md`. Confirm ports: UI **5173**, API **8010**, Mongo **27018**, Qdrant **6335**. Confirm folders: `integrated-frontend`, `integrated-backend`.

### Step 2 — Unit tests
Run isolated functions that students and the judge actually depend on:

- Passwords and JWT (`app/auth/security.py`, `validate_password_strength`)
- Pydantic request bodies (`app/schemas.py`)
- Gate 1 structural checks (MCQ / keypoints / summary / practice)
- Chat and resource **decide** (retry vs persist)
- PDF reject-before-ingest (`validate_pdf`)
- Cleaning, TOC skip, chunk metadata
- HTTP error mapping (`app/errors.py`)
- Frontend **contracts** (paths and `errorMessage` behaviour described in source)

Command:

```bash
pytest testing/unit -q
```

Each suite is one file named `test_<name>.py`. We commit and push **after each suite is green**.

### Step 3 — Integration tests
Stand up a **slim FastAPI app** (same routers, **no** lifespan, so no GGUF warm-up). Mock Mongo user store and document/job services.

Prove:

- Register 201 + token
- Weak password 400
- Duplicate email 409
- Login failure 401 (same message either way)
- `/api/auth/me` 401 without Bearer, 200 with a valid token
- Documents/chat/resources 401 when anonymous
- Bad PDF 400 with the engine message
- Upload 202 `{document, job_id}` when the service is mocked

Command:

```bash
pytest testing/integration -q
```

### Step 4 — User acceptance tests
A person (or optional live HTTP) walks the student path on a **running** stack.

1. `docker compose up -d` in `integrated-backend/`
2. `uvicorn server:app --port 8010` (JWT_SECRET_KEY in `.env`)
3. `npm run dev` in `integrated-frontend/` (VITE_API_BASE_URL=`http://localhost:8010`)
4. Follow `uat/UAT_CHECKLIST.md` and tick A-01 … A-10

Automated live tests:

```bash
set LEARNMATE_UAT=1
set LEARNMATE_API_URL=http://localhost:8010
pytest testing/uat -q
```

Without the env flag, UAT tests **skip** (so CI without Docker still passes).

The existing `integrated-backend/scripts/smoke_test.py` is an E2E script; its default URL is **8000** (a known bug). UAT must pass `--base-url http://localhost:8010` if you use that script.

### Step 5 — Record
Append the pytest summary to `RESULTS.md` (date, command, passed/failed/skipped).

### Step 6 — Push
```bash
git push -u origin testing
```
Never `git push origin main` for this work.

---

## 2. Pass / fail rules

| Result | Meaning |
|--------|---------|
| Unit/integration fail | Product logic or contract broken — fix or document a known gap |
| UAT skip | Stack not running — not a product fail |
| UAT fail with stack up | Real user-facing defect |
| Known gap (mode badge, resource scores) | Record on the checklist; do not “pass” by pretending the UI shows them |

---

## 3. Isolation rules

- Unit tests **must not** require Docker or model files.
- Integration tests **must not** start `server.py` lifespan.
- Do not call `get_generator_llm()` / `get_judge_llm()` in this folder.
- Do not write secrets into the repo. `conftest.py` uses a dummy JWT only if `.env` has none.

---

## 4. Mapping to academic terms

| Course term | In this repo |
|-------------|--------------|
| Unit testing | `testing/unit/` |
| Integration testing | `testing/integration/` |
| User acceptance testing | `testing/uat/` + checklist |
| Regression | Re-run pytest after any `integrated-*` change |
| Smoke / E2E | `scripts/smoke_test.py` (live models) — not part of the default pytest gate |

---

## 5. Commit convention on `testing`

One commit per test **name** (suite file), for example:

- `test: unit U-01 password hashing and JWT`
- `test: integration I-01 auth API`
- `test: uat checklist and optional live HTTP`

Push after each of those commits so `origin/testing` shows the history step by step.
