"""
The two entry points every agent uses to reach a model.

    get_generator_llm()   Qwen2.5-3B by default -- writes chat replies and resources
    get_judge_llm()       Llama-3.2-3B by default -- scores what the generator wrote

Both roles are built by the same `_build`, from the same kinds of settings; the only
difference between them is which config block is passed in. That is what makes swapping
Qwen for the finetuned model -- or for Gemini -- two lines of .env rather than a code
change. Three backends implement the same BaseChatModel surface:

    llamacpp   a local GGUF in this process          llamacpp.py
    http       an OpenAI-compatible served endpoint  http_api.py
    gemini     the Google API                        gemini.py

The two models are deliberately different families. A judge sharing the generator's
weights rates its own output style highly, and the retry loop stops firing.
"""

from pathlib import Path
import time
from typing import Callable, Optional

from .. import config
from . import catalog
from .download import ensure_gguf
from .gemini import GeminiChatModel
from .http_api import HttpChatModel
from .llamacpp import LlamaCppChatModel
from .runtime import unload_llama

# Wrappers, not weights -- see runtime.py for the layer below this one. Keyed by role and
# sampling settings, so asking for the generator at two temperatures makes two cheap
# wrapper objects that share a single loaded model.
_LLM_CACHE = {}

# Which generator GGUF is currently resident. llama.cpp holds one mutable context per
# file; switching model_id unloads this before loading the next.
_LOADED_GENERATOR_PATH: Optional[str] = None


def _build(role: str, backend: str, model: str, repo: str, filename: str,
           chat_format: str, n_ctx: int, api_url: str, api_key: str,
           temperature: float, max_tokens: int):
    """Construct the chat model one role's configuration describes."""
    if backend == "http":
        return HttpChatModel(
            base_url=api_url,
            model_name=model,
            api_key=api_key or None,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    if backend == "gemini":
        if not config.GEMINI_API_KEY:
            raise ValueError(
                f"The {role} backend is 'gemini' but GEMINI_API_KEY is not set. Add it to "
                f".env, or set LEARNMATE_{role.upper()}_BACKEND=llamacpp to run locally."
            )
        # The role's model setting doubles as the Gemini model id. A GGUF path left over
        # from the llamacpp default is meaningless to the API, so say so here rather than
        # letting it surface as a 404 from Google.
        if model.endswith(".gguf") or "/" in model or "\\" in model:
            raise ValueError(
                f"The {role} backend is 'gemini' but LEARNMATE_{role.upper()}_MODEL is "
                f"{model!r}, which is a local file path. Set it to a Gemini model id, "
                f"e.g. 'gemini-2.0-flash'."
            )
        return GeminiChatModel(
            api_key=config.GEMINI_API_KEY,
            model_name=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    if backend != "llamacpp":
        raise ValueError(
            f"Unknown {role} backend {backend!r}; expected 'llamacpp', 'http' or 'gemini'."
        )

    # ensure_gguf downloads on first use, so this is where a fresh checkout blocks for a
    # few minutes -- not somewhere deep inside a generation.
    return LlamaCppChatModel(
        gguf_path=ensure_gguf(model, repo, filename),
        n_ctx=n_ctx,
        n_threads=config.N_THREADS,
        n_gpu_layers=config.N_GPU_LAYERS,
        chat_format=chat_format or None,
        temperature=temperature,
        max_tokens=max_tokens,
    )


def _norm_path(path: str) -> str:
    try:
        resolved = Path(path)
        return str(resolved.resolve()) if resolved.exists() else str(resolved)
    except Exception:
        return str(path)


def _drop_generator_wrappers() -> None:
    for key in list(_LLM_CACHE):
        if key[0] == "generator":
            _LLM_CACHE.pop(key, None)


def resolve_generator_settings(model_id: Optional[str] = None):
    """
    Backend settings for one generator request.

    Omitted `model_id` uses LEARNMATE_GENERATOR_MODEL exactly as before. A named id must
    exist in models_registry.yaml; experimental entries are allowed only when their GGUF
    is actually on disk, and they never become the implicit default.
    """
    if not model_id:
        return {
            "id": None,
            "backend": config.GENERATOR_BACKEND,
            "model": config.GENERATOR_MODEL,
            "repo": config.GENERATOR_REPO,
            "filename": config.GENERATOR_FILE,
            "chat_format": config.GENERATOR_CHAT_FORMAT,
            "n_ctx": config.GENERATOR_N_CTX,
            "api_url": config.GENERATOR_API_URL,
            "api_key": config.GENERATOR_API_KEY,
        }

    entry = catalog.get_entry(model_id)
    if entry is None:
        raise ValueError(
            f"Unknown model_id {model_id!r}. GET /api/models lists the ones this server "
            "can load."
        )
    if not entry.get("available"):
        raise ValueError(
            f"Model {model_id!r} ({entry.get('display_name')}) is listed but its GGUF is "
            f"not on disk at {entry.get('resolved_path')}. Build or copy the file first."
        )
    return {
        "id": entry["id"],
        "backend": "llamacpp",
        "model": entry["resolved_path"],
        "repo": "",
        "filename": "",
        "chat_format": entry.get("chat_format") or "",
        "n_ctx": int(entry.get("context_length") or config.GENERATOR_N_CTX),
        "api_url": config.GENERATOR_API_URL,
        "api_key": config.GENERATOR_API_KEY,
        "experimental": bool(entry.get("experimental")),
        "display_name": entry.get("display_name"),
    }


def get_generator_llm(temperature: Optional[float] = None, max_tokens: int = 1024,
                      model_id: Optional[str] = None,
                      on_progress: Optional[Callable[[str], None]] = None):
    """
    The model that writes chat replies and study resources.

    Warmer than the judge on purpose: at temperature 0 a regeneration returns almost
    exactly the attempt that was just rejected, which defeats the retry loop.

    `model_id` selects a registry entry. Switching GGUFs unloads the previous generator
    (the judge stays loaded) and reports the reload delay via `on_progress`.
    """
    global _LOADED_GENERATOR_PATH

    temp = 0.7 if temperature is None else temperature
    settings = resolve_generator_settings(model_id)
    model_path = _norm_path(settings["model"])
    loaded = _norm_path(_LOADED_GENERATOR_PATH) if _LOADED_GENERATOR_PATH else None
    key = ("generator", model_path, temp, max_tokens)

    if (settings["backend"] == "llamacpp"
            and loaded
            and loaded != model_path):
        label = settings.get("display_name") or model_id or model_path
        message = f"Loading generator ({label}) — this can take several seconds..."
        if on_progress:
            try:
                on_progress(message)
            except Exception:
                pass
        print(f"[*] {message}")
        started = time.time()
        _drop_generator_wrappers()
        unload_llama(_LOADED_GENERATOR_PATH)
        _LOADED_GENERATOR_PATH = None
        elapsed = round(time.time() - started, 1)
        follow = f"Unloaded previous generator in {elapsed}s; loading the requested model."
        if on_progress:
            try:
                on_progress(follow)
            except Exception:
                pass

    if key not in _LLM_CACHE:
        started = time.time()
        _LLM_CACHE[key] = _build(
            "generator", settings["backend"], model_path,
            settings["repo"], settings["filename"], settings["chat_format"],
            settings["n_ctx"], settings["api_url"], settings["api_key"],
            temp, max_tokens,
        )
        if settings["backend"] == "llamacpp":
            _LOADED_GENERATOR_PATH = model_path
            elapsed = round(time.time() - started, 1)
            if elapsed >= 1 and on_progress:
                try:
                    on_progress(f"Generator ready ({elapsed}s to load).")
                except Exception:
                    pass
    elif settings["backend"] == "llamacpp":
        _LOADED_GENERATOR_PATH = model_path
    return _LLM_CACHE[key]


def get_judge_llm(temperature: float = 0.0, max_tokens: int = 512):
    """The evaluator model. Temperature 0: a grade should not be a dice roll."""
    key = ("judge", temperature, max_tokens)
    if key not in _LLM_CACHE:
        _LLM_CACHE[key] = _build(
            "judge", config.JUDGE_BACKEND, config.JUDGE_MODEL,
            config.JUDGE_REPO, config.JUDGE_FILE, config.JUDGE_CHAT_FORMAT,
            config.JUDGE_N_CTX, config.JUDGE_API_URL, config.JUDGE_API_KEY,
            temperature, max_tokens,
        )
    return _LLM_CACHE[key]
