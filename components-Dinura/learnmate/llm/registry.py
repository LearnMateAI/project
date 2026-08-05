"""
The two entry points every agent uses to reach a model.

    get_generator_llm()   Qwen2.5-3B by default -- writes chat replies and resources
    get_judge_llm()       Llama-3.2-3B by default -- scores what the generator wrote

Both roles are built by the same `_build`, from the same kinds of settings; the only
difference between them is which config block is passed in. That is what makes swapping
Qwen for the finetuned model two lines of .env rather than a code change.

The two models are deliberately different families. A judge sharing the generator's
weights rates its own output style highly, and the retry loop stops firing.
"""

from typing import Optional

from .. import config
from .download import ensure_gguf
from .http_api import HttpChatModel
from .llamacpp import LlamaCppChatModel

# Wrappers, not weights -- see runtime.py for the layer below this one. Keyed by role and
# sampling settings, so asking for the generator at two temperatures makes two cheap
# wrapper objects that share a single loaded model.
_LLM_CACHE = {}


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

    if backend != "llamacpp":
        raise ValueError(
            f"Unknown {role} backend {backend!r}; expected 'llamacpp' or 'http'."
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


def get_generator_llm(temperature: Optional[float] = None, max_tokens: int = 1024):
    """
    The model that writes chat replies and study resources.

    Warmer than the judge on purpose: at temperature 0 a regeneration returns almost
    exactly the attempt that was just rejected, which defeats the retry loop.
    """
    temp = 0.7 if temperature is None else temperature
    key = ("generator", temp, max_tokens)
    if key not in _LLM_CACHE:
        _LLM_CACHE[key] = _build(
            "generator", config.GENERATOR_BACKEND, config.GENERATOR_MODEL,
            config.GENERATOR_REPO, config.GENERATOR_FILE, config.GENERATOR_CHAT_FORMAT,
            config.GENERATOR_N_CTX, config.GENERATOR_API_URL, config.GENERATOR_API_KEY,
            temp, max_tokens,
        )
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
