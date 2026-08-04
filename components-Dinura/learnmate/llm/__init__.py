"""
Model access for LearnMate.

`get_generator_llm()` and `get_judge_llm()` are the only entry points the agents use, so
which model runs and how it is reached stays a configuration question. Both are cached,
so importing them from several modules still loads each model once per process.
"""

import os
from pathlib import Path
from typing import Optional

from .. import config
from .chat_models import HttpChatModel, LlamaCppChatModel, parse_json_reply
from .embeddings import LearnMateEmbeddings, get_embeddings

__all__ = [
    "HttpChatModel",
    "LlamaCppChatModel",
    "LearnMateEmbeddings",
    "get_embeddings",
    "get_generator_llm",
    "get_judge_llm",
    "parse_json_reply",
]

_LLM_CACHE = {}


def ensure_gguf(path: str, repo_id: str, filename: str) -> str:
    """
    Return a local path to a GGUF file, downloading it on first use.

    A finetuned model supplied as a plain file is used as-is; the download only happens
    when the configured path does not exist and a repo is known.
    """
    target = Path(path)
    if target.exists():
        return str(target)

    from huggingface_hub import hf_hub_download

    models_dir = target.parent if target.parent.name else config.MODELS_DIR
    models_dir.mkdir(parents=True, exist_ok=True)
    print(f"[*] {target.name} not found locally; downloading from {repo_id} (~2 GB, once)...")

    return hf_hub_download(
        repo_id=repo_id,
        filename=filename,
        local_dir=str(models_dir),
        token=config.HF_TOKEN,
    )


def _build(role: str, backend: str, model: str, repo: str, filename: str,
           chat_format: str, n_ctx: int, api_url: str, api_key: str,
           temperature: float, max_tokens: int):
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
