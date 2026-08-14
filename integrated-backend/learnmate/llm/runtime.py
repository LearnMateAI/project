"""
The llama.cpp weight cache: loading GGUF models once, and releasing them cleanly.

Loading a 2 GB GGUF takes seconds and a copy of the weights in RAM. The generator and the
judge are two different models and both may be asked for from several modules, so what
gets cached -- and what the cache is keyed on -- decides whether this system uses 4 GB or
8 GB of RAM.

This is the lowest of the three caches in this package:

    runtime.py     _LLAMA_CACHE   the actual weights, keyed by file
    registry.py    _LLM_CACHE     the chat-model wrappers, keyed by role and sampling
    embeddings.py  _MODEL_CACHE   the sentence-transformers model

Asking for the generator at two temperatures makes two wrappers that share one set of
weights, because only the wrapper layer has temperature in its key.
"""

import atexit
from typing import Any, Dict, Optional

from .. import config

# Keying on the path matters: the generator and the judge are different families on
# purpose -- a judge sharing the generator's weights rates its own output style highly
# and the retry loop never fires -- and a single shared slot would silently hand the
# judge whichever model happened to load first.
_LLAMA_CACHE: Dict[tuple, Any] = {}


def _load_llama(gguf_path: str, n_ctx: int, n_threads: Optional[int],
                n_gpu_layers: int, chat_format: Optional[str]):
    """
    Load (or reuse) a llama.cpp model.

    n_ctx and chat_format join the path in the key because both are baked into the loaded
    model: the same GGUF at a different context size is genuinely a different object and
    cannot be shared.

    The performance settings below are read from config here rather than passed in, unlike
    n_threads and n_gpu_layers above. They describe the machine, not the role -- there is
    no arrangement in which the generator wants flash attention and the judge does not --
    so they are process-wide by construction and cannot vary between two cache entries.
    That is also what keeps them out of the key.
    """
    key = (gguf_path, n_ctx, chat_format)
    if key not in _LLAMA_CACHE:
        from llama_cpp import Llama  # imported lazily so the HTTP backend needs no llama.cpp

        where = "GPU (all layers)" if n_gpu_layers < 0 else (
            f"GPU ({n_gpu_layers} layers)" if n_gpu_layers else "CPU")
        print(f"[*] Loading model: {gguf_path} on {where} (first load only)...")
        kwargs: Dict[str, Any] = {
            "model_path": gguf_path,
            "n_ctx": n_ctx,
            "n_threads": n_threads,
            # Prefill and decode are different shapes of work and scale differently; None
            # leaves llama.cpp's own default of every logical processor.
            "n_threads_batch": config.N_THREADS_BATCH,
            "n_gpu_layers": n_gpu_layers,
            "n_batch": config.N_BATCH,
            # Not merely a default when False: llama-cpp-python maps this onto ENABLED or
            # DISABLED, never llama.cpp's own AUTO, so leaving it off forces the slow
            # attention path even on a backend that supports the fast one.
            "flash_attn": config.FLASH_ATTN,
            "use_mlock": config.USE_MLOCK,
            "verbose": False,
        }
        # Left unset, llama.cpp reads the prompt template from the GGUF metadata, which is
        # correct for anything finetuned from a standard base.
        if chat_format:
            kwargs["chat_format"] = chat_format
        _LLAMA_CACHE[key] = Llama(**kwargs)
    return _LLAMA_CACHE[key]


@atexit.register
def _release_models() -> None:
    """
    Free the llama.cpp contexts while the interpreter is still standing.

    Left to the garbage collector, Llama.__del__ runs during interpreter shutdown and
    unwinds an ExitStack whose callbacks have already been torn down, printing a
    TypeError traceback after an otherwise clean exit. Closing here means the teardown
    happens while those modules still exist.
    """
    for model in list(_LLAMA_CACHE.values()):
        try:
            model.close()
        except Exception:
            pass
    _LLAMA_CACHE.clear()
