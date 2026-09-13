# LearnMateAI testing (branch `testing` only)

This folder is the **project test suite** for the live app (`integrated-frontend` + `integrated-backend`). It lives on the **`testing`** branch, copied from `main`. Do not merge these docs onto `main` unless the team agrees.

| Layer | What it proves | How to run |
|-------|----------------|------------|
| **Unit** | One function, no Docker, no GGUF | `pytest testing/unit -q` |
| **Integration** | Routers + error mapping + auth HTTP contract (Mongo mocked) | `pytest testing/integration -q` |
| **UAT** | Student journeys against a running stack | Checklist in `uat/` plus optional live HTTP |

## Quick start

From the **repository root**:

```bash
pip install -r testing/requirements.txt
pip install -r integrated-backend/requirements.txt
pytest testing/unit testing/integration -q
```

Live UAT (optional — needs Docker + API on **8010**):

```bash
set LEARNMATE_UAT=1
set LEARNMATE_API_URL=http://localhost:8010
pytest testing/uat -q
```

## Documents

| File | Purpose |
|------|---------|
| [PLAN.md](PLAN.md) | Test plan: scope, layers, cases, risks |
| [PROCESS.md](PROCESS.md) | Full process: how we test, commit, and report |
| [RESULTS.md](RESULTS.md) | Last recorded run (pass/fail) |
| [uat/UAT_CHECKLIST.md](uat/UAT_CHECKLIST.md) | Manual student journeys |

## Ports (do not use 8000)

| Service | Port |
|---------|------|
| Vite UI | 5173 |
| FastAPI | **8010** |
| MongoDB | 27018 |
| Qdrant | 6335 |

Root `frontend/` and `backend/` are **stale**. Tests target `integrated-*` only.
