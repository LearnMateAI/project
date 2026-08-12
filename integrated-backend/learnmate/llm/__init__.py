"""
Model access for LearnMate.

Three models, reached through three functions:

    get_generator_llm()   Qwen2.5-3B-Instruct   writes chat replies and study resources
    get_judge_llm()       Llama-3.2-3B-Instruct scores what the generator wrote
    get_embeddings()      all-MiniLM-L6-v2      embeds chunks at ingest, queries at retrieval

Those are the only entry points the agents use, so which model runs and how it is reached
stays a configuration question. All three are cached, so importing them from several
modules still loads each model once per process.

The two chat models share every line of code between them -- there is no Qwen class and no
Llama class. Which family loads is the GGUF path in config, nothing more. The embedding
model needs its own file because it implements a different LangChain interface
(`Embeddings`, not `BaseChatModel`).

Where things live, in reading order:

    registry.py     get_generator_llm / get_judge_llm -- the entry points, and the
                    per-role config that decides what they build
    llamacpp.py     backend 1  a local GGUF, in this process, with JSON grammars
    http_api.py     backend 2  a served OpenAI-compatible endpoint
    gemini.py       backend 3  the Google API, for when speed matters more than privacy
    messages.py     LangChain messages <-> the role/content dicts the backends want
    runtime.py      the GGUF weight cache, and releasing it cleanly at exit
    download.py     fetching a missing GGUF from Hugging Face on first use
    json_output.py  parse_json_reply -- recovering JSON from an unconstrained reply
    embeddings.py   LearnMateEmbeddings, the retrieval vectors

Caching happens at three separate layers, which is worth knowing before changing any of
them: `registry._LLM_CACHE` holds wrapper objects keyed by role and sampling settings,
`runtime._LLAMA_CACHE` holds the actual weights keyed by file, and
`embeddings._MODEL_CACHE` holds the sentence-transformers model. Two wrappers can share
one set of weights; that is the point of the split.

Heavy imports are all function-local -- llama_cpp, sentence_transformers,
huggingface_hub, requests -- so configuring the HTTP backend means llama.cpp never has to
be installed at all.
"""

from .download import ensure_gguf
from .embeddings import LearnMateEmbeddings, get_embeddings
from .gemini import GeminiChatModel
from .http_api import HttpChatModel
from .json_output import parse_json_reply
from .llamacpp import LlamaCppChatModel
from .registry import get_generator_llm, get_judge_llm

__all__ = [
    "GeminiChatModel",
    "HttpChatModel",
    "LearnMateEmbeddings",
    "LlamaCppChatModel",
    "ensure_gguf",
    "get_embeddings",
    "get_generator_llm",
    "get_judge_llm",
    "parse_json_reply",
]
