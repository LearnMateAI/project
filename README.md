# LearnMate AI

**A document-grounded, self-verifying study platform for Sri Lankan law students.**

University of Moratuwa · Faculty of Information Technology · Group Project, **Group 08**

| Member | Index | Main areas |
|---|---|---|
| W. T. D. Fernando | 230188L | LLM fine-tuning track, model registry and orchestration, retrieval and resource features, testing |
| N. G. T. S. Gamage | 230194C | React frontend, backend API, authentication (Keycloak), PDF pipeline |
| D. N. Ginige | 230202D | AI services, RAG and retrieval, judge/evaluator, integration, deployment |

**Live deployment:** <https://learnmateai.dinurag.dev>
**Source branch:** `production`, commit `e44d4c8` (merge of PR #32, 2026-10-05)

---

## 1. What it does

A student uploads their own course material and studies from it. Every answer is tied to the pages it came from and checked by a second model before it is trusted.

| The student… | LearnMate AI… |
|---|---|
| Uploads a PDF, Word (`.docx`), PowerPoint (`.pptx`) or LaTeX (`.tex`) file, up to 10 MB / 300 pages | Validates it, stores it once (SHA-256 de-duplication), extracts and cleans the text, splits it into chunks, embeds them, and marks the document **Ready** |
| Asks a question in chat | Rewrites follow-ups into standalone questions, retrieves and reranks passages, answers **with page citations**, and has a judge model from a different family score the reply (one regeneration if it fails) |
| Generates study material | MCQs (easy/medium/hard), short practice questions, key points (flashcards) and summaries (narrative/structured), from one passage or the whole document. Each is checked by structural rules and the judge |
| Opens Analytics | Activity counts, judge score distributions and a class "confusion heatmap" (aggregate-only, k-anonymous) |

## 2. Architecture

```
Browser (React SPA)
   │ HTTPS
   ▼
Nginx (TLS, :443) ──/auth──▶ Keycloak 26 (OIDC, RS256)
   │ /api                       ▲ JWKS
   ▼                            │
FastAPI backend ── 202 + job id ─┘
   │
   ├─ app/        web layer: routers → services → ownership checks → job queue
   └─ learnmate/  engine:
        ingestion → MongoDB (+GridFS) + Qdrant (+BM25)
        chat agent (LangGraph):     rewrite → [cache] → retrieve → generate → judge → retry? → persist
        resource agent (LangGraph): generate → check (rules + judge) → retry? → persist
        models: Qwen2.5-3B (writer) · Llama-3.2-3B (judge) · MiniLM embeddings · MiniLM cross-encoder reranker
```

- **Modular monolith**: one FastAPI service with a strict internal boundary. Routers never touch the engine or database directly, and the engine knows nothing about HTTP or users.
- **Asynchronous jobs**: upload, chat and generation return **HTTP 202** with a job id. The browser polls `GET /api/jobs/{id}`, which also streams the partial answer while it is written.
- **Swappable model serving**: every model is a LangChain `BaseChatModel`. Choose in-process llama.cpp (default), an OpenAI-compatible server (`llama-server`, vLLM) or Gemini through configuration only.

### Tech stack

| Layer | Technology |
|---|---|
| Frontend | React 19, Vite, Tailwind CSS 4, React Router 7, axios, keycloak-js |
| Backend | Python 3.13, FastAPI, Uvicorn, Pydantic |
| AI orchestration | LangChain, LangGraph |
| Models | llama-cpp-python (GGUF, Q4_K_M): Qwen2.5-3B-Instruct (generator), Llama-3.2-3B-Instruct (judge); sentence-transformers: all-MiniLM-L6-v2 (384-d), cross-encoder/ms-marco-MiniLM-L-6-v2, cross-encoder/quora-distilroberta-base |
| Data | MongoDB (+ GridFS), Qdrant |
| Identity | Keycloak 26 (OIDC, PKCE, RS256/JWKS) |
| Document parsing | PyMuPDF, python-docx, python-pptx |
| Delivery | Docker Compose, Nginx + Let's Encrypt, GitHub Actions, AWS EC2 via Systems Manager |

## 3. Repository layout

| Path | Contents |
|---|---|
| [`integrated-backend/`](integrated-backend/README.md) | FastAPI app (`app/`), the engine (`learnmate/`), Keycloak realm and theme, scripts, benchmarks (`eval/`), tests (`tests/`), dev Docker Compose |
| [`integrated-frontend/`](integrated-frontend/README.md) | React application (documents, reader, chat, resources, analytics) |
| [`model-Thevindu/`](model-Thevindu/README.md) | Offline ML track: legal corpus pipeline, QLoRA fine-tuning notebook, evaluation, acceptance gate, model card |
| [`testing/`](testing/README.md) | Test plan, unit, integration and UAT suites |
| [`docker-compose.yml`](docker-compose.yml) | Production stack (Nginx, frontend, backend, Keycloak, MongoDB, Qdrant) |
| [`nginx/`](nginx/default.conf.template) | TLS reverse proxy template |
| [`.github/workflows/deploy.yml`](.github/workflows/deploy.yml) | CI/CD pipeline |
| [`scripts/`](scripts/) | EC2 deploy script, Keycloak configuration, SSM parameter builder |
| [`AWS_DEPLOYMENT.md`](AWS_DEPLOYMENT.md) | One-time AWS setup and secrets |

## 4. Run it locally (development)

**Requirements:** Python 3.13, Node 18+ (CI uses 22), Docker, ~4 GB of disk for the two GGUF models, and 8-16 GB of RAM.

```bash
# 1. Databases + Keycloak (MongoDB :27018, Qdrant :6335, Keycloak :8081)
cd integrated-backend
docker compose up -d

# 2. Backend
python -m venv venv
venv\Scripts\pip install -r requirements.txt          # Linux/macOS: venv/bin/pip
copy .env.example .env                                  # set JWT_SECRET_KEY (any long random string)
venv\Scripts\python -m uvicorn server:app --reload --port 8010
#    → http://localhost:8010/api/health   ·   API docs: http://localhost:8010/docs
#    The two GGUF models (~4 GB) download from Hugging Face on first use.

# 3. Frontend
cd ../integrated-frontend
copy .env.example .env                                  # VITE_API_BASE_URL=http://localhost:8010
npm install
npm run dev                                              # → http://localhost:5173

# 4. Optional end-to-end smoke test (29 checks)
cd ../integrated-backend
venv\Scripts\python scripts\smoke_test.py data\Company-law-part1-notes.pdf --base-url http://127.0.0.1:8010
```

Development login: the imported Keycloak realm includes a test user, `dev` / `dev`.

## 5. Configuration highlights

All engine settings live in `integrated-backend/learnmate/config.py` and can be overridden from `.env`.

| Setting | Default | Meaning |
|---|---|---|
| `LEARNMATE_GENERATOR_BACKEND` / `_JUDGE_BACKEND` | `llamacpp` | `llamacpp`, `http` (llama-server / vLLM) or `gemini` |
| `LEARNMATE_CHUNK_SIZE` / `_OVERLAP` / `_MIN_CHUNK_CHARS` | 900 / 150 / 80 | Chunking |
| `LEARNMATE_RERANK_CANDIDATES` / `LEARNMATE_TOP_K` / `LEARNMATE_RERANK_THRESHOLD` | 20 / 3 / 0.5 | Retrieval → reranking → document ("pdf") vs general mode |
| `LEARNMATE_RETRIEVAL_STRATEGY` | `legacy` | Dense ANN ∪ BM25 (`rrf`, `dbsf`, `dense`, `bm25` available) |
| `LEARNMATE_EVALUATOR_THRESHOLD` / `LEARNMATE_MAX_ATTEMPTS` | 70 / 2 | Judge pass mark (1-100) and generation attempts |
| `LEARNMATE_CACHE_ENABLED` | off | Verified semantic answer cache |
| `JOB_QUEUE_BACKEND` | `memory` | `mongo` = lease-based queue for multiple workers/processes |
| `KEYCLOAK_ENABLED` | on in production | Verify Keycloak RS256 tokens |
| `OPENAI_API_KEY` | empty | Optional hosted "fast path"; when empty, everything runs locally |

## 6. Production deployment

**Target:** AWS EC2 (Ubuntu 22.04, t3.xlarge, 4 vCPU / 16 GB), Elastic IP, DNS `learnmateai.dinurag.dev`. Full setup is in [`AWS_DEPLOYMENT.md`](AWS_DEPLOYMENT.md).

**Stack** ([`docker-compose.yml`](docker-compose.yml)): Nginx (only service published, ports 80/443), frontend (static build), backend (FastAPI + llama.cpp, CPU), Keycloak 26 under `/auth`, MongoDB 7, Qdrant 1.18.1. Named volumes keep data, models and the Keycloak realm across deploys. TLS uses Let's Encrypt via certbot on the host; HTTP redirects to HTTPS.

**Deployment status (checked 2026-10-06):**

| Check | Result |
|---|---|
| `https://learnmateai.dinurag.dev/` | 200 OK |
| `GET /api/health` | `status: ok`. MongoDB ✔, Qdrant ✔, generator ✔, judge ✔ |
| Keycloak OIDC discovery (`/auth/realms/learnmate/.well-known/openid-configuration`) | 200 OK |

## 7. CI/CD (GitHub Actions)

Workflow: [`.github/workflows/deploy.yml`](.github/workflows/deploy.yml) ("Deploy Application"). It runs on every push to `production` and can also be started manually (`workflow_dispatch`). Concurrency is limited to one deploy at a time.

```
push to production
  └─ job: ci       Python 3.13 compile check of the backend · npm ci + production build of the frontend
  │                · docker compose config validation
  └─ job: deploy   (needs ci; GitHub environment "production")
                   AWS credentials → confirm the EC2 instance is online in SSM
                   → SSM Run Command: fetch the production branch onto the instance, then run
                   scripts/deploy-ec2.sh (write .env from secret, add swap, issue the TLS
                   certificate with certbot, docker compose up -d --build, wait for each service
                   to be healthy, configure Keycloak redirect URIs) → print logs, fail on error
```

No SSH key is stored in GitHub and port 22 is not used by the pipeline. Secrets (AWS keys, instance id, base64 `.env`) are GitHub **environment secrets**.

**Run evidence** (public Actions history, <https://github.com/LearnMateAI/project/actions>):

| Date (UTC) | Branch | Trigger | Commit | ci | deploy | Run |
|---|---|---|---|---|---|---|
| 2026-10-05 04:48 | production | manual | `e44d4c8` | ✔ success | ✔ success | [#37265076457](https://github.com/LearnMateAI/project/actions/runs/37265076457) |
| 2026-10-05 04:19 | production | push | `e44d4c8` | ✔ success | ✔ success | [#37263020785](https://github.com/LearnMateAI/project/actions/runs/37263020785) |
| 2026-10-04 03:43 | production | push | `edbd51b` | ✔ | ✔ | |
| 2026-10-01 06:58 | production | push | `6264535` | ✔ | ✔ | |

All 4 runs on `production` succeeded. The earlier failures on the `deployment` / `dinura-deployment` / `dinura-feedback-deploy` branches (Aug-Sep 2026) were the pipeline being built and debugged: SSM encoding, health checks, the MongoDB 8 → 7 kernel issue, Keycloak readiness.

A separate **`tests`** workflow (pytest on every push and PR) was built on branch `test/add-ci-workflow` and passed there (2026-09-19). It is **not yet part of the production pipeline**.

## 8. Testing

| Suite | Command | Latest result on this branch (2026-10-05) |
|---|---|---|
| Engine tests (`integrated-backend/tests`) | `cd integrated-backend && venv\Scripts\python -m pytest tests -q` | **111 collected: 108 passed, 3 skipped** (need a live MongoDB) |
| Unit + integration + UAT (`testing/`) | `python -m pytest testing/unit testing/integration testing/uat -q` (from repo root) | 94 passed, 4 skipped (live UAT needs `LEARNMATE_UAT=1`), **3 failed**: outdated error-message assertions from before multi-format upload; fixed on the `testing` branch |
| End-to-end smoke | `scripts/smoke_test.py` (needs the running stack) | 29/29 recorded (2026-09-21) |
| Benchmarks | `python -m eval.ir_bench` / `eval.cache_bench` / `eval.heatmap_bench` | Results in `integrated-backend/data/eval_results/` |

The unit and integration suites stub the model layer, so they run in seconds with no GGUF files or databases. They verify the contract around the models (routing, validation, ownership, retries), not model quality.

## 9. The fine-tuning track (`model-Thevindu/`)

An offline experiment to adapt a small model to Sri Lankan legal text, kept out of the request path:

- **Data:** 21 Sri Lankan legal documents → 19 parsed → 1,280 section-aware chunks → 2,534 grounded Q&A and summary pairs (a citation validator rejected 1 %). Split by chapter: 1,590 train / 339 val / 325 test, plus 280 pairs from four entirely held-out documents.
- **Training:** QLoRA on **Qwen2.5-1.5B-Instruct** (4-bit NF4, LoRA r=16, α=32, all 7 projection layers, 3 epochs, 597 steps) on a free Colab T4: 93.7 min, 3.39 GB peak VRAM.
- **Acceptance gate** (`03_testing_and_versioning/acceptance_thresholds.yaml`): accuracy ≥ 0.70, groundedness ≥ 0.85, hallucination ≤ 0.15, p95 latency ≤ 8 s, and it must beat the API fallback.
- **Result:** LLM-judge accuracy **0.557 / 0.621** (chapter / document held-out) against the 0.70 bar → **not promoted**. It is available only as an experimental, never-default registry entry (`legal-1.5b`). The live generator remains the stock Qwen2.5-3B.

Details: [`model-Thevindu/README.md`](model-Thevindu/README.md), the model card and training log in `model-Thevindu/04_docs/`.

## 10. Security and privacy

- **Authentication:** Keycloak OIDC with PKCE. The backend verifies RS256 tokens against Keycloak's JWKS (signature and issuer). Expired → 401, identity provider unreachable → 503.
- **Authorisation:** every document, session, resource and job request is checked for ownership. Documents you don't own return 404 (no existence leak); others return 403.
- **Uploads:** extension and MIME allow-list, magic-byte check, 10 MB and 300-page limits, encrypted and corrupt files rejected before any processing.
- **Privacy:** documents, vectors and models stay on the server by default. Class analytics are aggregate-only, with a k-anonymity floor of 3 students.
- **Known gaps:** no rate limiting; the token audience isn't verified; Keycloak runs in `start-dev` mode; tokens are kept in browser `localStorage`. Hardening (server-side judge policy, prompt-injection delimiters, rate limits) was developed on branch `docs/learnmate-ai-security-audit` and is pending merge.

## 11. Known limitations

- On CPU-only hardware a judged chat turn takes about 30-60 s (answers stream so the first words appear within seconds). A GPU or a served model with batching is the intended way to scale.
- No OCR: scanned PDFs without a text layer are rejected.
- Evaluation used small held-out sets and a simulated class; no external user study was run.
- Not legal advice: answers are study aids grounded in the uploaded material.

## 12. License and data

Sri Lankan statutes are public law. Some corpus sources are secondary consolidations whose terms must be reviewed before any dataset is redistributed, so the training data and adapter weights are not published. Model weights are downloaded from Hugging Face under their own licences (Qwen, Llama 3.2 Community License, Apache-2.0 sentence-transformers models).
