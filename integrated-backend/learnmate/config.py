"""
Central configuration for every LearnMate component.

Everything tunable lives here and is overridable through the environment, so switching
the generator model, pointing at a different MongoDB, or retuning a threshold never
means editing code. Values are read once at import.

The two settings that matter most:

    LEARNMATE_GENERATOR_BACKEND   "llamacpp" (in-process GGUF), "http" (served model)
                                  or "gemini" (the Google API)
    LEARNMATE_GENERATOR_MODEL     path to the GGUF, or the model name for http/gemini

Swapping Qwen2.5 for the finetuned model is a change to those two lines and nothing else.

This is the *engine* half of the configuration. The web layer's own settings -- the JWT
secret, the CORS origin, password rules -- live in app/config.py and read the same .env.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

PACKAGE_DIR = Path(__file__).resolve().parent
ROOT_DIR = PACKAGE_DIR.parent

# integrated-backend/.env holds HF_TOKEN, the JWT secret and any override below. Loaded
# here rather than in the server entry point because config is imported before anything
# reads an environment variable, which is what makes import order stop mattering.
load_dotenv(ROOT_DIR / ".env")


def _env(name: str, default: str) -> str:
    """Read an env var, treating an empty string as unset."""
    return (os.getenv(name) or "").strip() or default


def _env_int(name: str, default: int) -> int:
    try:
        return int(_env(name, str(default)))
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    try:
        return float(_env(name, str(default)))
    except ValueError:
        return default


# --- Filesystem ----------------------------------------------------------------------

# Where the GGUF model files live, and where a missing one is downloaded to.
# (There is deliberately no DATA_DIR: PDFs are read from wherever the caller names and
# then stored in MongoDB, so the project never has a directory it owns for them.)
MODELS_DIR = Path(_env("LEARNMATE_MODELS_DIR", str(ROOT_DIR / "models")))

# --- Generator model -----------------------------------------------------------------
# The model that writes chat replies and study resources.

GENERATOR_BACKEND = _env("LEARNMATE_GENERATOR_BACKEND", "llamacpp").lower()
GENERATOR_MODEL = _env("LEARNMATE_GENERATOR_MODEL",
                       str(MODELS_DIR / "qwen2.5-3b-instruct-q4_k_m.gguf"))

# Used only when the file above is missing and the backend is llamacpp.
GENERATOR_REPO = _env("LEARNMATE_GENERATOR_REPO", "Qwen/Qwen2.5-3B-Instruct-GGUF")
GENERATOR_FILE = _env("LEARNMATE_GENERATOR_FILE", "qwen2.5-3b-instruct-q4_k_m.gguf")

# A finetune with a non-standard prompt template needs its chat format named here
# (e.g. "chatml", "llama-3"). Empty lets llama.cpp read it from the GGUF metadata,
# which is correct for anything finetuned from a standard base.
GENERATOR_CHAT_FORMAT = _env("LEARNMATE_GENERATOR_CHAT_FORMAT", "")

GENERATOR_N_CTX = _env_int("LEARNMATE_GENERATOR_N_CTX", 4096)

# Base URL for the "http" backend, e.g. an OpenAI-compatible server in front of the
# finetuned model. Points at whatever local-model-api/ or finetuned-model-api/ serves.
GENERATOR_API_URL = _env("LEARNMATE_GENERATOR_API_URL", "http://localhost:8001/v1")
GENERATOR_API_KEY = _env("LEARNMATE_GENERATOR_API_KEY", "")

# --- Judge model ---------------------------------------------------------------------
# Deliberately a different family from the generator: a judge sharing the generator's
# weights rates its own output style highly and the retry loop never fires.

JUDGE_BACKEND = _env("LEARNMATE_JUDGE_BACKEND", "llamacpp").lower()
JUDGE_MODEL = _env("LEARNMATE_JUDGE_MODEL",
                   str(MODELS_DIR / "Llama-3.2-3B-Instruct-Q4_K_M.gguf"))
JUDGE_REPO = _env("LEARNMATE_JUDGE_REPO", "bartowski/Llama-3.2-3B-Instruct-GGUF")
JUDGE_FILE = _env("LEARNMATE_JUDGE_FILE", "Llama-3.2-3B-Instruct-Q4_K_M.gguf")
JUDGE_CHAT_FORMAT = _env("LEARNMATE_JUDGE_CHAT_FORMAT", "")

# Judging is short-output / long-input: a resource plus its source text must fit.
JUDGE_N_CTX = _env_int("LEARNMATE_JUDGE_N_CTX", 8192)
JUDGE_API_URL = _env("LEARNMATE_JUDGE_API_URL", "http://localhost:8002/v1")
JUDGE_API_KEY = _env("LEARNMATE_JUDGE_API_KEY", "")

# None lets llama.cpp auto-detect physical cores.
N_THREADS = int(_env("LEARNMATE_N_THREADS", "0")) or None
N_GPU_LAYERS = _env_int("LEARNMATE_N_GPU_LAYERS", 0)

# --- Gemini --------------------------------------------------------------------------
# Only read when a role's backend is "gemini". The model name for that role comes from
# GENERATOR_MODEL / JUDGE_MODEL, which double as the Gemini model id -- set them to
# something like "gemini-2.0-flash" when you switch a role over.
#
# Keep the two roles on different models here too: a judge sharing the generator's weights
# rates its own output style highly, and the retry loop stops firing.

GEMINI_API_KEY = _env("GEMINI_API_KEY", "")

# --- Embeddings ----------------------------------------------------------------------

EMBEDDING_MODEL = _env("LEARNMATE_EMBEDDING_MODEL", "all-MiniLM-L6-v2")

# --- MongoDB -------------------------------------------------------------------------
# An external server, not an embedded file store. A plain mongodb:// URI works; an
# Atlas mongodb+srv:// URI additionally unlocks server-side $vectorSearch.
#
# 27018, not the conventional 27017: this project runs its own MongoDB container
# (`docker compose up -d mongo`) with its own named volume, because 27017 on this machine
# is answered by a native service shared with two other projects. Sharing a server means
# sharing a failure -- another project's `docker compose down -v` would take LearnMate's
# PDFs, sessions and generated resources with it.

MONGODB_URI = _env("LEARNMATE_MONGODB_URI", "mongodb://localhost:27018")
MONGODB_DB = _env("LEARNMATE_MONGODB_DB", "learnmate")

COLL_DOCUMENTS = "documents"
COLL_CHUNKS = "chunks"
COLL_PAGES = "pages"
COLL_RESOURCES = "resources"
COLL_EVALUATIONS = "evaluations"
COLL_CHAT_TURNS = "chat_turns"
# One record per session, holding the PDF that session is bound to.
COLL_SESSIONS = "sessions"
# Registered accounts, and who may see which document. `documents` is keyed by the hash of
# the file's bytes so one PDF is stored and embedded once however many people upload it --
# which means ownership cannot be a field on it, and lives in its own collection instead.
COLL_USERS = "users"
COLL_USER_DOCUMENTS = "user_documents"
# Background work: everything a request cannot wait for. See app/jobs/.
COLL_JOBS = "jobs"
GRIDFS_BUCKET = "pdfs"

# Name of the Atlas vector index over chunks.embedding. Only consulted by the "mongodb"
# vector backend, and ignored on a community server where it falls back to NumPy.
VECTOR_INDEX_NAME = _env("LEARNMATE_VECTOR_INDEX", "chunk_vector_index")

# --- Vector database -----------------------------------------------------------------
# Where the chunk embeddings live. MongoDB always holds the PDFs, page text, generated
# resources and history regardless of this setting; only the vectors move.
#
#   qdrant    a Qdrant server over HTTP -- a real HNSW index, filtering and scoring
#             server-side. The default.
#   mongodb   vectors in the same MongoDB as everything else. Atlas $vectorSearch when
#             available, otherwise exact NumPy scoring. Useful when you do not want a
#             second service running.
VECTOR_BACKEND = _env("LEARNMATE_VECTOR_BACKEND", "qdrant").lower()

# Server mode only. A URL, never a directory: `QdrantClient(path=...)` runs Qdrant inside
# the process and locks the directory, so only one process could use the corpus at a time.
#
# 6335 rather than Qdrant's conventional 6333, because this machine already runs a
# separate Qdrant on 6333 for another project. docker-compose.yml publishes the matching
# port; override this if you move it.
QDRANT_URL = _env("LEARNMATE_QDRANT_URL", "http://localhost:6335")
QDRANT_API_KEY = _env("LEARNMATE_QDRANT_API_KEY", "")
QDRANT_COLLECTION = _env("LEARNMATE_QDRANT_COLLECTION", "learnmate_chunks")
QDRANT_TIMEOUT = _env_int("LEARNMATE_QDRANT_TIMEOUT", 30)

# Points per upsert/scroll request. Large enough to keep ingestion off the round-trip
# treadmill, small enough that one request stays well inside Qdrant's payload limit.
QDRANT_BATCH_SIZE = _env_int("LEARNMATE_QDRANT_BATCH_SIZE", 128)

# --- Uploads ---------------------------------------------------------------------------
# One PDF per session. Embedding a document is the expensive part of this system -- a few
# thousand chunks through a CPU embedding model -- so a session is bound to the first PDF
# ingested into it and a second upload is refused rather than silently paying that cost
# again. A new PDF means a new session id.
# Set LEARNMATE_ONE_PDF_PER_SESSION=0 to lift the restriction.
ONE_PDF_PER_SESSION = _env("LEARNMATE_ONE_PDF_PER_SESSION", "1").lower() not in (
    "0", "false", "no", "off")

# Largest PDF accepted, in MB. A 10 MB textbook is already a few thousand chunks and
# several minutes of embedding on CPU; past that the ingest looks hung rather than slow.
MAX_PDF_MB = _env_float("LEARNMATE_MAX_PDF_MB", 10.0)
MAX_PDF_BYTES = int(MAX_PDF_MB * 1_048_576)

# Second ceiling on the same upload, in pages. Size alone does not bound the work: a
# 3 MB scan of 800 pages is a short file and a very long ingest. 300 is the SRS figure.
MAX_PAGE_COUNT = _env_int("LEARNMATE_MAX_PAGE_COUNT", 300)

# --- Retrieval and chunking ----------------------------------------------------------

CHUNK_SIZE = _env_int("LEARNMATE_CHUNK_SIZE", 900)
CHUNK_OVERLAP = _env_int("LEARNMATE_CHUNK_OVERLAP", 150)

# Shortest chunk worth embedding; below this it is a running head or a stray caption.
MIN_CHUNK_CHARS = _env_int("LEARNMATE_MIN_CHUNK_CHARS", 80)

TOP_K = _env_int("LEARNMATE_TOP_K", 4)

# Cosine similarity below which retrieved context is treated as irrelevant and the chat
# agent answers from general knowledge instead.
RELEVANCE_THRESHOLD = _env_float("LEARNMATE_RELEVANCE_THRESHOLD", 0.25)

# --- Agent behaviour -----------------------------------------------------------------

EVALUATOR_THRESHOLD = _env_int("LEARNMATE_EVALUATOR_THRESHOLD", 70)

# One generation plus at most one regeneration. Raising this is not just slower: a 3B
# judge tends to oscillate rather than converge over more rounds.
MAX_ATTEMPTS = _env_int("LEARNMATE_MAX_ATTEMPTS", 2)

# Rolling chat history depth, in user+assistant pairs.
MAX_HISTORY_TURNS = _env_int("LEARNMATE_MAX_HISTORY_TURNS", 6)

# How much document text a resource-generation run is allowed to use as its source.
# Must leave room in the context window for the prompt and the generated JSON.
MAX_SOURCE_CHARS = _env_int("LEARNMATE_MAX_SOURCE_CHARS", 6000)

HF_TOKEN = _env("HF_TOKEN", "") or None
