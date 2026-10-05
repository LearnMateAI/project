"""
Shared plumbing for every evaluation script: isolation, provenance, output.

    from eval.common import bootstrap
    bootstrap()                 # BEFORE anything imports learnmate
    from learnmate import ...

Isolation. learnmate/config.py reads its settings once, at import, and load_dotenv never
overrides a variable that is already set. So bootstrap() writes the evaluation's settings
into the environment first, and the engine then runs against:

    MongoDB   database `learnmate_eval` on the usual server   (never `learnmate`)
    Qdrant    the eval container on :6337                      (never the app's)
    models    the registry default Qwen2.5-3B generator        (never .env's finetune)

Provenance. Every result file carries the git commit, whether the tree was dirty, the
machine, the package versions, the non-secret LEARNMATE_* settings and a hash of the
generator's weights -- so a number in the paper can be traced to exactly what produced it.
"""

import hashlib
import json
import os
import platform
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional

BACKEND_DIR = Path(__file__).resolve().parents[1]
REPO_DIR = BACKEND_DIR.parent
DATA_DIR = BACKEND_DIR / "data"
CORPUS_DIR = DATA_DIR / "eval_corpus"
WORKLOAD_DIR = DATA_DIR / "eval_workload"
RESULTS_DIR = DATA_DIR / "eval_results"
PAPER_DIR = REPO_DIR / "paper"

EVAL_ENV = {
    "LEARNMATE_MONGODB_DB": "learnmate_eval",
    "LEARNMATE_QDRANT_URL": "http://127.0.0.1:6337",
    "LEARNMATE_QDRANT_COLLECTION": "eval_chunks_v2",
    "LEARNMATE_QDRANT_SCHEMA": "v2",
    "LEARNMATE_CACHE_COLLECTION": "eval_answer_cache",
    "LEARNMATE_GENERATOR_BACKEND": "llamacpp",
    "LEARNMATE_GENERATOR_MODEL": str(BACKEND_DIR / "models" / "qwen2.5-3b-instruct-q4_k_m.gguf"),
    "LEARNMATE_GENERATOR_REPO": "Qwen/Qwen2.5-3B-Instruct-GGUF",
    "LEARNMATE_GENERATOR_FILE": "qwen2.5-3b-instruct-q4_k_m.gguf",
    # Deterministic evaluation: strategy and cache are passed explicitly by each script.
    "LEARNMATE_RETRIEVAL_STRATEGY": "rrf",
    "API_WARM_UP": "0",
}

_SECRET_WORDS = ("KEY", "SECRET", "TOKEN", "PASSWORD")


def bootstrap(overrides: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    """Point the engine at the evaluation stores. Must run before `import learnmate`."""
    if "learnmate.config" in sys.modules:
        raise RuntimeError("bootstrap() must run before learnmate is imported")
    settings = {**EVAL_ENV, **(overrides or {})}
    # An explicit EVAL_<NAME> in the shell wins, so a run can be redirected without edits.
    for name in list(settings):
        if os.getenv(f"EVAL_{name}"):
            settings[name] = os.environ[f"EVAL_{name}"]
    os.environ.update(settings)
    os.chdir(BACKEND_DIR)
    if str(BACKEND_DIR) not in sys.path:
        sys.path.insert(0, str(BACKEND_DIR))
    return settings


def _git(*args: str) -> str:
    try:
        return subprocess.run(["git", *args], cwd=REPO_DIR, capture_output=True, text=True,
                              timeout=10).stdout.strip()
    except Exception:
        return ""


_HASHES: Dict[str, str] = {}


def file_sha256(path: str) -> Optional[str]:
    """SHA-256 of a (possibly multi-GB) file, cached per process."""
    if path in _HASHES:
        return _HASHES[path]
    target = Path(path)
    if not target.is_file():
        return None
    digest = hashlib.sha256()
    with target.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    _HASHES[path] = digest.hexdigest()
    return _HASHES[path]


def _cpu() -> str:
    if sys.platform == "darwin":
        try:
            return subprocess.run(["sysctl", "-n", "machdep.cpu.brand_string"],
                                  capture_output=True, text=True).stdout.strip()
        except Exception:
            pass
    return platform.processor() or platform.machine()


def provenance(hash_models: bool = False) -> Dict:
    """Where and with what a result was produced."""
    try:
        import psutil  # optional

        ram_gb = round(psutil.virtual_memory().total / 2 ** 30, 1)
    except Exception:
        ram_gb = None
    versions = {}
    for name in ("qdrant_client", "pymongo", "sentence_transformers", "torch", "sklearn",
                 "llama_cpp", "numpy"):
        try:
            module = __import__(name)
            versions[name] = getattr(module, "__version__", "?")
        except Exception:
            versions[name] = None
    settings = {name: value for name, value in sorted(os.environ.items())
                if name.startswith(("LEARNMATE_", "JOB_"))
                and not any(word in name for word in _SECRET_WORDS)}
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "git_commit": _git("rev-parse", "HEAD"),
        "git_dirty": bool(_git("status", "--porcelain")),
        "machine": {"platform": platform.platform(), "cpu": _cpu(),
                    "cores": os.cpu_count(), "ram_gb": ram_gb,
                    "python": platform.python_version()},
        "packages": versions,
        "settings": settings,
    }
    if hash_models:
        model = os.getenv("LEARNMATE_GENERATOR_MODEL", "")
        record["generator_sha256"] = file_sha256(model)
    return record


def run_dir(name: str) -> Path:
    path = RESULTS_DIR / name
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_json(path: Path, payload) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    return path


def read_jsonl(path: Path) -> List[Dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()]


def write_jsonl(path: Path, rows: Iterable[Dict]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, default=str) + "\n")
    return path


class Stopwatch:
    """`with Stopwatch() as t: ...; t.ms`"""

    def __enter__(self):
        self._start = time.perf_counter()
        return self

    def __exit__(self, *exc):
        self.ms = (time.perf_counter() - self._start) * 1000.0
        return False
