"""
LangChain chat models for the two ways a LearnMate model can be reached.

    LlamaCppChatModel   in-process GGUF through llama-cpp-python (CPU by default)
    HttpChatModel       an OpenAI-compatible /chat/completions endpoint

Both are real BaseChatModel implementations, so they compose with prompts, output
parsers and LangGraph nodes exactly like any other LangChain chat model, and both accept
the same `response_schema` kwarg.

That kwarg is the reason these exist rather than a stock integration. A 3B model asked
politely for JSON returns prose about half the time; llama.cpp can instead compile a JSON
schema into a decoding grammar so malformed output is impossible. Everything structured in
this project -- every generated resource, every verdict -- depends on it, and no stock
wrapper exposes it. Bind it like any other LangChain kwarg:

    llm.bind(response_schema=SCHEMA).invoke(messages)
"""

from __future__ import annotations

import atexit
import json
import re
from typing import Any, Dict, List, Optional

from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    ChatMessage,
    HumanMessage,
    SystemMessage,
)
from langchain_core.outputs import ChatGeneration, ChatResult

# One Llama instance per (path, n_ctx, chat_format). Loading a 2 GB GGUF takes seconds and
# a copy of the weights in RAM, so the generator and the judge must each load exactly once
# however many components ask for them. Keying on the path matters: the two models are
# different families on purpose, and a single shared slot would silently hand the judge
# whichever model happened to load first.
_LLAMA_CACHE: Dict[tuple, Any] = {}


def _load_llama(gguf_path: str, n_ctx: int, n_threads: Optional[int],
                n_gpu_layers: int, chat_format: Optional[str]):
    """Load (or reuse) a llama.cpp model."""
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


def _to_payload(messages: List[BaseMessage]) -> List[Dict[str, str]]:
    """Convert LangChain messages into the role/content dicts both backends expect."""
    role_map = {"human": "user", "ai": "assistant", "system": "system"}
    payload = []
    for message in messages:
        if isinstance(message, ChatMessage):
            role = message.role
        else:
            role = role_map.get(message.type, "user")
        payload.append({"role": role, "content": str(message.content)})
    return payload


def _as_result(text: str) -> ChatResult:
    return ChatResult(generations=[ChatGeneration(message=AIMessage(content=text or ""))])


class LlamaCppChatModel(BaseChatModel):
    """A local GGUF model, with optional grammar-constrained JSON output."""

    gguf_path: str
    n_ctx: int = 4096
    n_threads: Optional[int] = None
    n_gpu_layers: int = 0
    chat_format: Optional[str] = None
    temperature: float = 0.3
    max_tokens: int = 512

    @property
    def _llm_type(self) -> str:
        return "learnmate-llamacpp"

    @property
    def _identifying_params(self) -> Dict[str, Any]:
        return {"gguf_path": self.gguf_path, "n_ctx": self.n_ctx,
                "chat_format": self.chat_format}

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        llama = _load_llama(self.gguf_path, self.n_ctx, self.n_threads,
                            self.n_gpu_layers, self.chat_format)

        params: Dict[str, Any] = {
            "messages": _to_payload(messages),
            "max_tokens": kwargs.get("max_tokens", self.max_tokens),
            "temperature": kwargs.get("temperature", self.temperature),
        }
        if stop:
            params["stop"] = stop

        schema = kwargs.get("response_schema")
        if schema is not None:
            try:
                constrained = dict(params)
                constrained["response_format"] = {"type": "json_object", "schema": schema}
                result = llama.create_chat_completion(**constrained)
                return _as_result(result["choices"][0]["message"]["content"])
            except Exception:
                # Older llama-cpp-python builds have no grammar support. Fall through and
                # ask plainly; the callers all parse defensively.
                pass

        result = llama.create_chat_completion(**params)
        return _as_result(result["choices"][0]["message"]["content"])


class HttpChatModel(BaseChatModel):
    """
    An OpenAI-compatible chat endpoint, for when the model is served rather than loaded.

    This is the path the finetuned model takes if it ends up behind local-model-api/ or
    finetuned-model-api/ instead of shipping as a GGUF. `response_schema` is forwarded as
    OpenAI-style `response_format`; servers that reject it get a plain retry, so an
    endpoint without schema support still works.
    """

    base_url: str
    model_name: str = "local-model"
    api_key: Optional[str] = None
    temperature: float = 0.3
    max_tokens: int = 512
    timeout: int = 300

    @property
    def _llm_type(self) -> str:
        return "learnmate-http"

    @property
    def _identifying_params(self) -> Dict[str, Any]:
        return {"base_url": self.base_url, "model_name": self.model_name}

    def _post(self, body: Dict[str, Any]) -> str:
        import requests

        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        response = requests.post(f"{self.base_url.rstrip('/')}/chat/completions",
                                 json=body, headers=headers, timeout=self.timeout)
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        body: Dict[str, Any] = {
            "model": self.model_name,
            "messages": _to_payload(messages),
            "max_tokens": kwargs.get("max_tokens", self.max_tokens),
            "temperature": kwargs.get("temperature", self.temperature),
        }
        if stop:
            body["stop"] = stop

        schema = kwargs.get("response_schema")
        if schema is not None:
            try:
                constrained = dict(body)
                constrained["response_format"] = {
                    "type": "json_schema",
                    "json_schema": {"name": "response", "schema": schema, "strict": True},
                }
                return _as_result(self._post(constrained))
            except Exception:
                pass

        return _as_result(self._post(body))


def parse_json_reply(raw: str) -> Any:
    """
    Parse a model reply that is supposed to be JSON.

    Grammar-constrained output is already clean, but the unconstrained fallback path can
    wrap it in code fences or a sentence of preamble, so pull the first JSON value out of
    whatever came back. Raises ValueError when there is nothing parseable, which callers
    treat as a failed attempt rather than shipping a placeholder downstream.
    """
    if isinstance(raw, (dict, list)):
        return raw

    text = (raw or "").strip()
    try:
        return json.loads(text)
    except (ValueError, TypeError):
        pass

    # Strip a ```json fence if one is present, then take the outermost braces/brackets.
    fenced = re.sub(r"^```(?:json)?|```$", "", text, flags=re.MULTILINE).strip()
    match = re.search(r"[\[{].*[\]}]", fenced, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except ValueError:
            pass

    raise ValueError(f"Could not parse model output as JSON: {text[:200]}")
