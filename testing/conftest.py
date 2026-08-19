"""Shared fixtures. Environment is set before any app import."""

from __future__ import annotations

import os
import sys
from pathlib import Path

TESTING_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTING_DIR.parent
BACKEND_ROOT = REPO_ROOT / "integrated-backend"
FRONTEND_ROOT = REPO_ROOT / "integrated-frontend"

# Dummy secret only if the developer has not set one. load_dotenv will not override this.
os.environ.setdefault(
    "JWT_SECRET_KEY",
    "unit-test-secret-do-not-use-in-production-32b",
)
os.environ.setdefault("API_WARM_UP", "0")
os.environ.setdefault("API_WARM_MODELS", "0")
os.environ.setdefault("KEYCLOAK_ENABLED", "0")

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

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
