"""Shared fixtures. Environment and light package stubs before any app import.

`learnmate/__init__.py` (and several subpackage inits) import LangGraph, ChatAgent and
the LLM registry. Unit tests must not load GGUFs. We register namespace packages so
submodules such as `learnmate.evaluator.mcq_rules` import without running those inits.
"""

from __future__ import annotations

import os
import sys
import types
from pathlib import Path

TESTING_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTING_DIR.parent
BACKEND_ROOT = REPO_ROOT / "integrated-backend"
FRONTEND_ROOT = REPO_ROOT / "integrated-frontend"
LEARNMATE_DIR = BACKEND_ROOT / "learnmate"

os.environ.setdefault(
    "JWT_SECRET_KEY",
    "unit-test-secret-do-not-use-in-production-32b",
)
os.environ.setdefault("API_WARM_UP", "0")
os.environ.setdefault("API_WARM_MODELS", "0")
os.environ.setdefault("KEYCLOAK_ENABLED", "0")

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _namespace(fullname: str, path: Path) -> types.ModuleType:
    """A package in sys.modules that does not execute __init__.py."""
    existing = sys.modules.get(fullname)
    if existing is not None and getattr(existing, "__path__", None):
        return existing
    mod = types.ModuleType(fullname)
    mod.__path__ = [str(path)]
    mod.__package__ = fullname
    mod.__file__ = str(path / "__init__.py")
    sys.modules[fullname] = mod
    return mod


# Must run before `import learnmate` / `import app`.
_namespace("learnmate", LEARNMATE_DIR)
_namespace("learnmate.chat_agent", LEARNMATE_DIR / "chat_agent")
_namespace("learnmate.resource_agent", LEARNMATE_DIR / "resource_agent")
_namespace("learnmate.evaluator", LEARNMATE_DIR / "evaluator")
_namespace("learnmate.ingestion", LEARNMATE_DIR / "ingestion")
_namespace("learnmate.storage", LEARNMATE_DIR / "storage")
_namespace("learnmate.llm", LEARNMATE_DIR / "llm")
_namespace("app.routers", BACKEND_ROOT / "app" / "routers")


class _Stub:
    """Stand-in so routers can import engine entry points without loading GGUFs."""

    def __init__(self, *args, **kwargs):
        pass


def _not_in_unit_tests(*args, **kwargs):
    raise RuntimeError("This engine entry point is stubbed in pytest; it is not called.")


from learnmate.resource_agent.tasks import TASK_NAMES  # noqa: E402
from learnmate.ingestion.sessions import require_kind  # noqa: E402
from learnmate.ingestion.source_text import build_source_text  # noqa: E402
from learnmate.ingestion.validate import validate_pdf  # noqa: E402

sys.modules["learnmate.chat_agent"].ChatAgent = _Stub
sys.modules["learnmate.resource_agent"].TASK_NAMES = TASK_NAMES
sys.modules["learnmate.resource_agent"].generate_resource = _not_in_unit_tests
sys.modules["learnmate.resource_agent"].generate_document_items = _not_in_unit_tests
sys.modules["learnmate.resource_agent"].summarize_document = _not_in_unit_tests
sys.modules["learnmate.ingestion"].require_kind = require_kind
sys.modules["learnmate.ingestion"].build_source_text = build_source_text
sys.modules["learnmate.ingestion"].validate_pdf = validate_pdf
sys.modules["learnmate.ingestion"].ingest_pdf = _not_in_unit_tests

import pytest  # noqa: E402


@pytest.fixture
def repo_root() -> Path:
    return REPO_ROOT


@pytest.fixture
def backend_root() -> Path:
    return BACKEND_ROOT


@pytest.fixture
def frontend_root() -> Path:
    return FRONTEND_ROOT
