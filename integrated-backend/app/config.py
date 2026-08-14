"""
The web layer's settings.

The engine's own settings -- which model, which database, which thresholds -- live in
learnmate/config.py and are read there. This file holds only what a *server* needs and the
engine has no opinion about: who may call it, how long a token lasts, where the browser is.

Both read the same integrated-backend/.env, and importing learnmate.config is what loads
it. That import is deliberate rather than a second `load_dotenv()` call here: it means
there is exactly one place the file is read, and no module can accidentally read an
environment variable before it has been.
"""

import os

# Imported for its side effect as much as its values: learnmate.config calls load_dotenv()
# at import, so every os.getenv below sees the .env file.
from learnmate import config as engine_config

ROOT_DIR = engine_config.ROOT_DIR


def _env(name: str, default: str = "") -> str:
    """Read an env var, treating an empty string as unset."""
    return (os.getenv(name) or "").strip() or default


def _env_int(name: str, default: int) -> int:
    try:
        return int(_env(name, str(default)))
    except ValueError:
        return default


def _env_bool(name: str, default: bool) -> bool:
    return _env(name, "1" if default else "0").lower() not in ("0", "false", "no", "off")


# --- CORS ------------------------------------------------------------------------------
# The Vite dev server, by default. A comma-separated list is accepted so a deployed
# frontend and a local one can both be allowed at once.
_ORIGINS = _env("FRONTEND_ORIGIN", "http://localhost:5173")
FRONTEND_ORIGINS = [origin.strip() for origin in _ORIGINS.split(",") if origin.strip()]

# --- Tokens ----------------------------------------------------------------------------
# No default, on purpose. A fallback secret is worse than a missing one: it works in
# development, ships to production unnoticed, and every token it ever signed is forgeable
# by anyone who has read the source. Startup fails loudly instead -- see require_secret().
JWT_SECRET_KEY = _env("JWT_SECRET_KEY")
JWT_EXPIRY_HOURS = _env_int("JWT_EXPIRY_HOURS", 24)
JWT_ALGORITHM = "HS256"

# --- Passwords -------------------------------------------------------------------------
# Enforced server-side, whatever the form does.
PASSWORD_MIN_LENGTH = _env_int("PASSWORD_MIN_LENGTH", 8)

# --- Start-up ----------------------------------------------------------------------------
# Load the embedding model and the ingestion import chain on a background thread at start-up
# so the first upload does not have to -- about sixteen seconds, against roughly one second
# of actual work for a small PDF. Set API_WARM_UP=0 to skip it, which is worth doing if you
# are restarting constantly and not uploading. See app/jobs/worker.py:warm_up.
WARM_UP_ON_START = _env_bool("API_WARM_UP", True)

# --- Listings --------------------------------------------------------------------------
MAX_DOCUMENTS = _env_int("API_MAX_DOCUMENTS", 200)
MAX_RESOURCES = _env_int("API_MAX_RESOURCES", 100)
MAX_JOBS = _env_int("API_MAX_JOBS", 50)


def require_secret() -> None:
    """
    Fail startup when the token secret is missing.

    Called from the app's lifespan rather than at import so that `import app.config` --
    which tooling and tests do -- does not explode, while a server that could issue
    forgeable tokens never gets as far as accepting a request.
    """
    if not JWT_SECRET_KEY:
        raise RuntimeError(
            "JWT_SECRET_KEY is not set. Add it to integrated-backend/.env -- any long "
            "random string will do, e.g. `python -c \"import secrets; "
            "print(secrets.token_hex(32))\"`."
        )
