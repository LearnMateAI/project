# Where to edit — live app vs your ML track

Work in these folders only. Root `frontend/` and `backend/` are **stale**. `components-Dinura/` is the engine origin; the live copy is `integrated-backend/learnmate/`.

---

## Live product (demo these)

| If you want to change… | Edit this |
|---|---|
| Routes, public vs protected pages | `integrated-frontend/src/App.jsx` |
| API base URL (must be **8010**) | `integrated-frontend/.env` ← copy `.env.example` |
| Auth token + 401 redirect | `integrated-frontend/src/api/client.js` |
| Login / register | `src/pages/login.jsx`, `register.jsx` |
| Upload, 10 MB cap, Processing→Ready | `src/pages/documents.jsx`, `src/components/DocumentsCard.jsx` |
| Generate MCQ / summary / keypoints / practice | `src/components/ResourcesPanel.jsx` |
| Job polling / progress text | `src/hooks/useJob.js`, `src/api/jobs.js` |
| Chat UI + streaming | `src/pages/chat.jsx`, `src/components/StreamingMessage.jsx`, `ChatMessage.jsx` |
| **PDF vs general-knowledge badge (missing — restore here)** | `ChatMessage.jsx` — backend already sends `turn.mode` |
| Resource viewer / quiz | `src/pages/resources/ResourceView.jsx`, `McqQuiz.jsx` |
| **Judge score on a resource (data exists, UI omitted)** | `ResourceView.jsx` — `accepted`, `score`, `threshold`, `reasoning` |
| Analytics KPIs | `src/pages/analytics.jsx` — `stats.evaluation` is unused |
| Settings that do not persist | `src/pages/myaccountsettings.jsx` |

| Backend change | Edit this |
|---|---|
| FastAPI app, CORS, `/api/health` | `integrated-backend/server.py` |
| JWT secret (no default) | `integrated-backend/.env` ← `JWT_SECRET_KEY`; `app/config.py` |
| Auth routes | `app/routers/auth.py`, `app/auth/users.py` |
| Upload 202 + job | `app/routers/documents.py` |
| Chat 202 + job | `app/routers/chat.py`, `app/services/chat.py` |
| Resources 202 + job | `app/routers/resources.py` |
| **One worker thread** (do not make a pool) | `app/jobs/worker.py` |
| Chat graph | `learnmate/chat_agent/graph.py` |
| Retrieve + rerank | `learnmate/chat_agent/retrieve.py` |
| Judge | `learnmate/evaluator/` |
| **Swap generator to a served LoRA** (after a pass only) | `integrated-backend/.env`: `LEARNMATE_GENERATOR_BACKEND=http`, `LEARNMATE_GENERATOR_API_URL`, `LEARNMATE_GENERATOR_MODEL` — implemented in `learnmate/llm/http_api.py` + `registry.py` |
| Docker DBs | `integrated-backend/docker-compose.yml` — Mongo **27018**, Qdrant **6335** |
| Smoke test default port (still **8000** — wrong) | `scripts/smoke_test.py` → should be **8010** |

---

## Your track (defend these)

| If you want to change… | Edit this |
|---|---|
| Which statutes / subjects | `01_dataset_pipeline/manifests/target_corpus_manifest.csv` |
| Subject taxonomy | `config/subject_areas.yaml` |
| Parse / chunk / TOC drop | `preprocess_dataset.py` |
| Pair generation + GI-001 | `generate_training_pairs.py`, `validate_pairs.py` |
| Chapter split + strict holdout | `split_dataset.py` (`--group_by chapter --strict_holdout`) |
| Train LoRA | `02_finetuning/finetune_qwen25_lora.ipynb` |
| Gate numbers | `03_testing_and_versioning/acceptance_thresholds.yaml` |
| Live eval | `evaluate_candidate.ipynb` |
| Re-score without GPU | `rescore_eval.py` |
| Pass/fail history | `version_registry.csv` |
| Promote (do not, yet) | `promotion_checklist.md` |
| Lineage / GI-001 / GI-002 | `04_docs/dataset_lineage.md` |

**Do not edit to “force a pass”:** `acceptance_thresholds.yaml`.  
**Do not load** `qwen25-lora-20260815-090709` into the app.

---

## Demo ports (say these if asked)

| Service | Port |
|---|---|
| Vite UI | **5173** |
| FastAPI | **8010** (not 8000) |
| MongoDB | **27018** |
| Qdrant | **6335** |
| Optional served LoRA | `8001` in `.env.example` — unused until a candidate passes |
