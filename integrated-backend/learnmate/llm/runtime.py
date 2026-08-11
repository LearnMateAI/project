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
    """
    key = (gguf_path, n_ctx, chat_format)
    if key not in _LLAMA_CACHE:
        from llama_cpp import Llama  # imported lazily so the HTTP backend needs no llama.cpp

        print(f"[*] Loading model: {gguf_path} (first load only)...")
        kwargs: Dict[str, Any] = {
            "model_path": gguf_path,
            "n_ctx": n_ctx,
            "n_threads": n_threads,
            "n_gpu_layers": n_gpu_layers,
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
