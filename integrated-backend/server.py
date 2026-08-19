"""
LearnMate backend.

    uvicorn server:app --reload --port 8000

Two halves, and the boundary between them is worth knowing before changing anything:

    learnmate/   the engine -- ingestion, retrieval, the two LangGraph agents, the
                 evaluator, and all persistence. Knows nothing about HTTP or users.
    app/         the web layer -- accounts, access control, the job queue, the endpoints.

Start the databases first:

    docker compose up -d          MongoDB on 27018, Qdrant on 6335

Then check everything is reachable before uploading anything:

    GET /api/health

The first generation of a fresh install downloads two GGUF models (~4 GB, once) and is
slow for that reason. Every subsequent one is slow for the honest reason: a 3B model on a
CPU. That is why nothing heavy happens inside a request -- see app/jobs/.
"""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import config
from app.errors import register_error_handlers
from app.jobs import shutdown as stop_worker
from app.jobs import start_worker, warm_up
from app.routers import analytics, auth, chat, documents, jobs, resources
from learnmate import config as engine_config
from learnmate.storage import ensure_indexes
from learnmate.storage.mongo import StorageUnavailable

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
)
logger = logging.getLogger("learnmate.api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Start-up and shut-down.

    By default this does *not* load the generator or the judge. Both are ~2 GB and lazily
    cached inside the engine, so loading them here adds a minute to every restart and makes
    `--reload` unusable. In development the first job that needs one pays that cost instead.

    On a machine that is being demonstrated rather than developed on, that default is the
    wrong way round -- the cost does not go away, it lands inside the first question
    somebody asks. API_WARM_MODELS=1 loads both at boot instead. See
    app/jobs/worker.py:warm_up, which owns both decisions.

    The 90 MB embedding model is a different question and is warmed either way, on a
    background thread. It costs nothing on the request path and takes about sixteen seconds
    off the first upload, which is otherwise almost entirely import and model-load time
    rather than work.

    Mongo is contacted, though: indexes are created on first connect, and a database that
    is down should be a clear failure at startup rather than a confusing 500 on the first
    upload.
    """
    config.require_secret()

    try:
        ensure_indexes()
        logger.info("MongoDB ready at %s (database %r)",
                    engine_config.MONGODB_URI, engine_config.MONGODB_DB)
    except StorageUnavailable as exc:
        # Not fatal: the server still starts and /api/health reports the problem, which is
        # more useful than a process that exits before anyone can ask it what is wrong.
        logger.error("MongoDB is unreachable: %s", exc)

    start_worker()
    # Decides for itself which of its two phases to run, from API_WARM_UP and
    # API_WARM_MODELS, and returns immediately when neither is set. Gating it here as well
    # would mean one flag could silently disable the other.
    warm_up()
    logger.info("Generator: %s (%s) | Judge: %s (%s) | Vectors: %s",
                engine_config.GENERATOR_BACKEND, engine_config.GENERATOR_MODEL,
                engine_config.JUDGE_BACKEND, engine_config.JUDGE_MODEL,
                engine_config.VECTOR_BACKEND)

    yield

    stop_worker()


app = FastAPI(
    title="LearnMate API",
    version="1.0.0",
    description="Upload a PDF, ask it questions, generate study material from it.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.FRONTEND_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_error_handlers(app)

app.include_router(auth.router)
app.include_router(documents.router)
app.include_router(resources.router)
app.include_router(chat.router)
app.include_router(jobs.router)
app.include_router(analytics.router)


@app.get("/")
def root():
    """Where to start."""
    return {
        "name": "LearnMate API",
        "health": "/api/health",
        "docs": "/docs",
    }


@app.get("/api/health")
def health():
    """
    Is everything this depends on actually reachable?

    Both databases, both model files, and what is configured. Run it first whenever
    something misbehaves -- an unreachable Qdrant and a missing GGUF fail at completely
    different moments otherwise, and both look like "generation is broken".
    """
    checks = {}

    # --- MongoDB: the corpus. Nothing works without it. --------------------------------
    try:
        ensure_indexes()
        checks["mongodb"] = {"ok": True, "uri": engine_config.MONGODB_URI,
                             "database": engine_config.MONGODB_DB}
    except Exception as exc:
        checks["mongodb"] = {"ok": False, "uri": engine_config.MONGODB_URI,
                             "error": str(exc)}

    # --- Vector store: retrieval. Chat and topic search need it. -----------------------
    # ping() rather than count(): counting would create the collection on a fresh install,
    # and creating it needs the embedding model's dimension -- so a health check would
    # pull 90 MB of weights into memory just to answer whether Qdrant is up.
    try:
        from learnmate.storage.vectors import get_vector_store

        checks["vectors"] = {"ok": True, **get_vector_store().ping()}
    except Exception as exc:
        checks["vectors"] = {"ok": False, "backend": engine_config.VECTOR_BACKEND,
                             "error": str(exc)}

    # --- Models: present, or downloaded on first use? ----------------------------------
    # Checked as files rather than by loading them: loading is ~2 GB and several seconds,
    # which is not something a health check should do.
    def model_check(backend: str, model: str, repo: str = "", filename: str = "") -> dict:
        if backend == "llamacpp":
            path = Path(model)
            if path.exists():
                note = None
            elif repo and filename:
                note = "Not downloaded yet; fetched on first use (~2 GB)."
            else:
                # No repo means a locally-built GGUF -- the merged finetune -- which will
                # never appear on its own. Saying it downloads on first use would send
                # somebody off to wait for a download that is not going to happen.
                note = ("Missing, and no download source is configured. If this is the "
                        "finetuned model, build it: python scripts/build_finetuned_gguf.py")
            return {"ok": path.exists(), "backend": backend, "model": model, "note": note}
        if backend == "gemini":
            return {"ok": bool(engine_config.GEMINI_API_KEY), "backend": backend,
                    "model": model,
                    "note": None if engine_config.GEMINI_API_KEY
                            else "GEMINI_API_KEY is not set."}
        return {"ok": True, "backend": backend, "model": model, "note": None}

    checks["generator"] = model_check(engine_config.GENERATOR_BACKEND,
                                      engine_config.GENERATOR_MODEL,
                                      engine_config.GENERATOR_REPO,
                                      engine_config.GENERATOR_FILE)
    checks["judge"] = model_check(engine_config.JUDGE_BACKEND, engine_config.JUDGE_MODEL,
                                  engine_config.JUDGE_REPO, engine_config.JUDGE_FILE)

    # A missing GGUF is not "degraded": it downloads on first use, or -- for a locally
    # built one -- the note above says how to build it. Either way the fix is a file on
    # disk, and the per-model check already reports it.
    # Only the two databases decide whether this server can do its job right now.
    healthy = checks["mongodb"]["ok"] and checks["vectors"]["ok"]

    return {"status": "ok" if healthy else "degraded", "checks": checks}
