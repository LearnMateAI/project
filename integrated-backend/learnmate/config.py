"""
Central configuration for every LearnMate component.

Everything tunable lives here and is overridable through the environment, so switching
the generator model, pointing at a different MongoDB, or retuning a threshold never
means editing code. Values are read once at import.

The two settings that matter most:

    LEARNMATE_GENERATOR_BACKEND   "llamacpp" (in-process GGUF), "http" (served model)
                                  or "gemini" (the Google API)
    LEARNMATE_GENERATOR_MODEL     path to the GGUF, or the model name for http/gemini

Swapping the base Qwen2.5 for the domain finetune from model-Thevindu is a change to the
second of those lines and nothing else -- see the generator block below, and
scripts/build_finetuned_gguf.py for how the GGUF it names is produced.

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


def _env_optional(name: str, default: str) -> str:
    """
    Read a setting whose *empty* value is a meaningful choice, not a request for the
    default.

    `_env` cannot express "no value": setting `FOO=` in .env gives back the default,
    because an empty string is indistinguishable from an unset one there. That is the
    right rule for a port or a URI, where empty means nothing useful.

    It is the wrong rule for the download source of a locally-built model. Emptying
    *_REPO / *_FILE is how someone says "this GGUF is built here and exists in no
    repository" -- and under `_env` that instruction silently reverts to the *base
    model's* repo, so a missing finetune downloads the stock model and answers in its
    place. Absent still means the default; present-but-empty now means empty.
    """
    raw = os.getenv(name)
    return default if raw is None else raw.strip()


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


def _env_bool(name: str, default: bool) -> bool:
    """Read a flag. Anything but the recognised falsey words counts as on."""
    return _env(name, "1" if default else "0").lower() not in (
        "0", "false", "no", "off")


# --- Filesystem ----------------------------------------------------------------------

# Where the GGUF model files live, and where a missing one is downloaded to.
# (There is deliberately no DATA_DIR: PDFs are read from wherever the caller names and
# then stored in MongoDB, so the project never has a directory it owns for them.)
MODELS_DIR = Path(_env("LEARNMATE_MODELS_DIR", str(ROOT_DIR / "models")))

# --- Generator model -----------------------------------------------------------------
# The model that writes chat replies and study resources.
#
# Two models can fill this role, and .env decides which:
#
#   models/qwen2.5-3b-instruct-q4_k_m.gguf          the stock base, the default here
#   models/learnmate-legal-qwen2.5-1.5b-q8_0.gguf   the domain finetune from model-Thevindu
#
# The finetune is the ML track's `qwen25-lora-20260815-090709` LoRA merged into its
# Qwen2.5-1.5B-Instruct base and converted to GGUF -- see scripts/build_finetuned_gguf.py,
# which produces it, and the .json sidecar it writes beside the weights for provenance.
#
# The default below stays on the base model on purpose. It is the one a fresh checkout can
# actually obtain: the finetune exists in no repository, is built locally from an adapter
# that the ML track gitignores, and cannot be downloaded on demand. A default pointing at
# a file that a new clone has no way to get is a broken first run.
#
# Note what changes with the finetune beyond the domain tuning: it is 1.5B where the base
# is 3B, so it is a smaller general-purpose model, and it did NOT pass the acceptance gate
# in model-Thevindu/03_testing_and_versioning/ (see version_registry.csv -- it loses to the
# API fallback on both accuracy and groundedness). Running it is a deliberate choice; the
# rollback is one line in .env.

GENERATOR_BACKEND = _env("LEARNMATE_GENERATOR_BACKEND", "llamacpp").lower()
GENERATOR_MODEL = _env("LEARNMATE_GENERATOR_MODEL",
                       str(MODELS_DIR / "qwen2.5-3b-instruct-q4_k_m.gguf"))

# Used only when the file above is missing and the backend is llamacpp. Leave both empty
# for a locally-built model: ensure_gguf then reports the missing file and how to build it,
# rather than downloading a *different* model and running that instead.
GENERATOR_REPO = _env_optional("LEARNMATE_GENERATOR_REPO", "Qwen/Qwen2.5-3B-Instruct-GGUF")
GENERATOR_FILE = _env_optional("LEARNMATE_GENERATOR_FILE", "qwen2.5-3b-instruct-q4_k_m.gguf")

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
JUDGE_REPO = _env_optional("LEARNMATE_JUDGE_REPO", "bartowski/Llama-3.2-3B-Instruct-GGUF")
JUDGE_FILE = _env_optional("LEARNMATE_JUDGE_FILE", "Llama-3.2-3B-Instruct-Q4_K_M.gguf")
JUDGE_CHAT_FORMAT = _env("LEARNMATE_JUDGE_CHAT_FORMAT", "")

# Judging is short-output / long-input: a resource plus its source text must fit.
JUDGE_N_CTX = _env_int("LEARNMATE_JUDGE_N_CTX", 8192)
JUDGE_API_URL = _env("LEARNMATE_JUDGE_API_URL", "http://localhost:8002/v1")
JUDGE_API_KEY = _env("LEARNMATE_JUDGE_API_KEY", "")

# --- llama.cpp runtime -----------------------------------------------------------------
# How the two GGUFs are executed. These describe the *machine*, not the role, so both the
# generator and the judge are loaded with the same values -- see llm/runtime.py, which
# reads them directly rather than having them threaded through every model wrapper.
#
# This block is the difference between a 40-second reply and a 6-second one, and none of
# it is portable: the right values on the Windows laptop and on the demo MacBook are not
# the same numbers. .env carries one set commented out beside the other.

# None lets llama.cpp pick, which is cpu_count() // 2. That is a reasonable guess on a
# uniform CPU and a poor one on a hybrid: counting Intel's E-cores as if they were P-cores
# spreads the work onto cores that finish late and hold everyone else up. Set it explicitly
# after measuring rather than trusting either number.
N_THREADS = _env_int("LEARNMATE_N_THREADS", 0) or None

# Prefill is a separate knob from decode because it is a different shape of work: reading
# the prompt is a big parallel matrix multiply that scales with cores, while writing tokens
# is memory-bound and stops scaling early. llama.cpp defaults this to *all* logical
# processors. None keeps that default.
N_THREADS_BATCH = _env_int("LEARNMATE_N_THREADS_BATCH", 0) or None

# How many layers run on the GPU. 0 is pure CPU; **-1 offloads every layer**, which is what
# a Metal Mac wants -- a 3B Q4 model is ~2 GB and fits in unified memory whole. Anything in
# between splits the model and pays a transfer per token for the privilege, so the useful
# settings are really just 0 and -1.
N_GPU_LAYERS = _env_int("LEARNMATE_N_GPU_LAYERS", 0)

# Prompt-processing batch size: how many tokens are prefilled per pass. Bigger means fewer,
# larger matrix multiplies, which is what a GPU wants; on CPU the gain flattens out and the
# scratch buffers grow. 512 is llama.cpp's own default and a sane floor.
N_BATCH = _env_int("LEARNMATE_N_BATCH", 512)

# Flash attention. Worth knowing that this is *not* a no-op when left off: llama.cpp's own
# default is AUTO (enable it where the backend supports it), but llama-cpp-python's boolean
# only reaches ENABLED or DISABLED -- so not setting it forces attention onto the slow path
# even on Metal, where it is a clear win. Off by default here to keep CPU behaviour exactly
# as it was; turn it on with the GPU.
FLASH_ATTN = _env_bool("LEARNMATE_FLASH_ATTN", False)

# Pin the weights in RAM so the OS cannot page them out. Worth it when a model is used
# steadily and there is memory to spare; on a laptop that is also running two databases and
# a browser it can push everything else into swap instead. Needs privileges to take effect,
# and llama.cpp warns and carries on when it cannot.
USE_MLOCK = _env_bool("LEARNMATE_USE_MLOCK", False)

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

# Some retrieval models are trained with an instruction prefix on the query side only --
# bge-*-en-v1.5 and the e5-* family are the common ones -- and lose a noticeable amount of
# accuracy without it. MiniLM is not one of them, so both default to empty.
#
# Switching to bge-small-en-v1.5 (same 384 dims, same speed, 512-token window instead of
# MiniLM's 256) means setting:
#     LEARNMATE_EMBEDDING_MODEL=BAAI/bge-small-en-v1.5
#     LEARNMATE_EMBEDDING_QUERY_PREFIX=Represent this sentence for searching relevant passages:
# ...and then re-ingesting every document, because vectors from two different models are
# not comparable. See EMBEDDING_MISMATCH below for what happens if you forget.
EMBEDDING_QUERY_PREFIX = _env("LEARNMATE_EMBEDDING_QUERY_PREFIX", "")
EMBEDDING_DOC_PREFIX = _env("LEARNMATE_EMBEDDING_DOC_PREFIX", "")

# --- Reranking -------------------------------------------------------------------------
# A cross-encoder re-scores the chunks the vector search returned, reading each one
# *together with* the question instead of comparing two independently-made vectors. That
# is a much better judgement of relevance, and on a 22M-parameter model it costs ~100ms
# against a generation measured in tens of seconds.
#
# It also pays for itself twice: better chunks mean fewer replies the judge rejects, and
# every rejection costs a full regeneration.

RERANK_ENABLED = _env_bool("LEARNMATE_RERANK_ENABLED", True)
RERANK_MODEL = _env("LEARNMATE_RERANK_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2")

# How many chunks the vector search hands the reranker. The reranker is only allowed to
# reorder what retrieval already found, so this is the real recall ceiling -- TOP_K is
# just how many survive. Larger costs a few ms per candidate and nothing else.
RERANK_CANDIDATES = _env_int("LEARNMATE_RERANK_CANDIDATES", 20)

# Cross-encoder scores are raw logits; they are put through a sigmoid so this threshold
# lives in [0, 1] like the cosine one it replaces. 0.5 is the model's own decision
# boundary. This is what decides "pdf" vs "general" mode whenever reranking is on.
RERANK_THRESHOLD = _env_float("LEARNMATE_RERANK_THRESHOLD", 0.5)

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
ONE_PDF_PER_SESSION = _env_bool("LEARNMATE_ONE_PDF_PER_SESSION", True)

# Largest PDF accepted, in MB. A 10 MB textbook is already a few thousand chunks and
# several minutes of embedding on CPU; past that the ingest looks hung rather than slow.
MAX_PDF_MB = _env_float("LEARNMATE_MAX_PDF_MB", 10.0)
MAX_PDF_BYTES = int(MAX_PDF_MB * 1_048_576)

# Second ceiling on the same upload, in pages. Size alone does not bound the work: a
# 3 MB scan of 800 pages is a short file and a very long ingest. 300 is the SRS figure.
MAX_PAGE_COUNT = _env_int("LEARNMATE_MAX_PAGE_COUNT", 300)

# --- Retrieval and chunking ----------------------------------------------------------

# A chunk longer than the embedding model's window is silently truncated -- the tail is
# simply not in the vector, and nothing warns you. all-MiniLM-L6-v2 stops at 256 word
# pieces, so this number is really a bet on how much text 900 characters tokenises to.
#
# The bet holds, and it was checked rather than assumed. Tokenising every chunk in this
# project's corpus (755 chunks over four PDFs) against MiniLM's own tokeniser: nothing was
# truncated, median 133 tokens, longest 235 against the 256 limit. The recursive splitter
# breaks at sentence boundaries well before the character ceiling, which is what keeps the
# real distribution far under it.
#
# Worth re-checking rather than trusting if the corpus changes character: 235/256 is 92% of
# the budget, so a document with denser tokenisation -- tables, code, heavy numerals -- has
# little room left. Lowering this to ~600 buys that margin back, at the cost of re-ingesting
# every document for a gain that, on the corpus measured here, is zero.
CHUNK_SIZE = _env_int("LEARNMATE_CHUNK_SIZE", 900)
CHUNK_OVERLAP = _env_int("LEARNMATE_CHUNK_OVERLAP", 150)

# Shortest chunk worth embedding; below this it is a running head or a stray caption.
MIN_CHUNK_CHARS = _env_int("LEARNMATE_MIN_CHUNK_CHARS", 80)

# How many chunks reach the prompt. With reranking on these are the best of
# RERANK_CANDIDATES rather than the vector search's own top 4, so a smaller number carries
# more signal -- and every chunk dropped is prefill saved twice over, once in the
# generator and again in the judge.
TOP_K = _env_int("LEARNMATE_TOP_K", 3)

# Cosine similarity below which retrieved context is treated as irrelevant and the chat
# agent answers from general knowledge instead.
#
# Only consulted when reranking is off or unavailable -- RERANK_THRESHOLD decides the mode
# otherwise. Note that this number is model-specific: raw cosine under MiniLM puts even
# unrelated text around 0.1-0.3, whereas bge-* compresses everything much higher. Retune it
# against your own score distribution rather than carrying it across a model change.
RELEVANCE_THRESHOLD = _env_float("LEARNMATE_RELEVANCE_THRESHOLD", 0.25)

# --- Agent behaviour -----------------------------------------------------------------

EVALUATOR_THRESHOLD = _env_int("LEARNMATE_EVALUATOR_THRESHOLD", 70)

# Retrieval modes whose chat replies skip the LLM judge entirely. Comma-separated; empty
# judges everything, which is what this system did before the gate existed.
#
# "general" by default, and that is a measurement rather than a preference. Across the 21
# chat verdicts logged by this project so far:
#
#     pdf mode      17 verdicts, scores spread 1 to 100, median 60, 35% passing
#     general mode   4 verdicts, every one of them exactly 100, 18-27s each
#
# The judge is doing real work in pdf mode -- it has the retrieved chunks to check claims
# against, and it rejects roughly two thirds of what it reads. In general mode it has no
# source material and nothing to check, and it answers 100 every time: a number with no
# variance cannot gate anything, and buying it costs twenty-odd seconds a turn.
#
# So this skips the judge exactly where it was not judging. Note the small sample -- four
# general-mode verdicts is thin evidence, and the honest reading is "no sign of any signal"
# rather than "proven useless". Every skip is still logged (stage="gate"), so widening or
# reverting this stays an evidence-based decision. See chat_agent/gate.py.
JUDGE_GATE_MODES = frozenset(
    mode.strip().lower()
    for mode in _env("LEARNMATE_JUDGE_GATE_MODES", "general").split(",")
    if mode.strip()
)

# One generation plus at most one regeneration. Raising this is not just slower: a 3B
# judge tends to oscillate rather than converge over more rounds.
MAX_ATTEMPTS = _env_int("LEARNMATE_MAX_ATTEMPTS", 2)

# Rolling chat history depth, in user+assistant pairs.
MAX_HISTORY_TURNS = _env_int("LEARNMATE_MAX_HISTORY_TURNS", 6)

# How much document text a resource-generation run is allowed to use as its source.
# Must leave room in the context window for the prompt and the generated JSON.
MAX_SOURCE_CHARS = _env_int("LEARNMATE_MAX_SOURCE_CHARS", 6000)

HF_TOKEN = _env("HF_TOKEN", "") or None

# --- Feature adders (additive; env-off restores prior behaviour) ----------------------

# Hybrid retrieve: ANN (as today) plus BM25, merged before the existing reranker.
# Default on for this branch. Set LEARNMATE_HYBRID_BM25=0 to restore ANN-only.
HYBRID_BM25 = _env_bool("LEARNMATE_HYBRID_BM25", True)
BM25_ANN_KEEP = _env_int("LEARNMATE_BM25_ANN_KEEP", 15)
BM25_TOP_K = _env_int("LEARNMATE_BM25_TOP_K", 10)

# Per-document BM25 corpus (chunk text), stored in Mongo alongside pages/chunks.
COLL_BM25 = "bm25_chunks"

# Selectable generators. LEARNMATE_GENERATOR_MODEL remains the fallback when model_id
# is omitted. A failed-gate LoRA may be listed as experimental; it must not be default.
MODELS_REGISTRY_PATH = Path(_env(
    "LEARNMATE_MODELS_REGISTRY",
    str(PACKAGE_DIR / "models_registry.yaml"),
))
