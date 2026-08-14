"""
Backend 1 of 2: a local GGUF model, run in this process through llama-cpp-python.

The default path for both roles. `learnmate/models/` holds the two GGUFs -- Qwen2.5-3B for
the generator, Llama-3.2-3B for the judge -- and which one this class loads is decided
entirely by the `gguf_path` it is constructed with. There is no Qwen class and no Llama
class; the family is a configuration value.

This is a real BaseChatModel, so it composes with prompts, output parsers and LangGraph
nodes exactly like any stock LangChain chat model.
"""

from typing import Any, Dict, Iterator, List, Optional

from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessageChunk, BaseMessage
from langchain_core.outputs import ChatGenerationChunk, ChatResult

from .messages import _as_result, _to_payload
from .runtime import _load_llama


class LlamaCppChatModel(BaseChatModel):
    """A local GGUF model, with optional grammar-constrained JSON output."""

    gguf_path: str
    n_ctx: int = 4096
    n_threads: Optional[int] = None
    n_gpu_layers: int = 0
    chat_format: Optional[str] = None
    # Defaults only. Every call site in this project passes its own -- see the kwargs
    # handling in _generate below.
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
        """
        The one method BaseChatModel requires. `.invoke(...)` arrives here.

        Weights come from the shared cache, so constructing several of these is cheap --
        only the first one to name a given GGUF actually loads it.
        """
        llama = _load_llama(self.gguf_path, self.n_ctx, self.n_threads,
                            self.n_gpu_layers, self.chat_format)

        # Per-call kwargs win over the constructor defaults. This is how the chat agent
        # gets temperature 0.0 for rewriting and 0.3 for generating out of one cached
        # model instead of building a new one for each.
        params: Dict[str, Any] = {
            "messages": _to_payload(messages),
            "max_tokens": kwargs.get("max_tokens", self.max_tokens),
            "temperature": kwargs.get("temperature", self.temperature),
        }
        if stop:
            params["stop"] = stop

        # --- Grammar-constrained JSON ---------------------------------------------------
        # The reason this class exists rather than a stock integration. A 3B model asked
        # politely for JSON returns prose about half the time; llama.cpp can instead
        # compile the schema into a decoding grammar, so malformed output is impossible.
        # Everything structured here -- every resource, every verdict -- depends on it.
        schema = kwargs.get("response_schema")
        if schema is not None:
            try:
                constrained = dict(params)
                constrained["response_format"] = {"type": "json_object", "schema": schema}
                result = llama.create_chat_completion(**constrained)
                return _as_result(result["choices"][0]["message"]["content"])
            except Exception:
                # Older llama-cpp-python builds have no grammar support. Fall through and
                # ask plainly; the callers all parse defensively (see json_output.py).
                pass

        result = llama.create_chat_completion(**params)
        return _as_result(result["choices"][0]["message"]["content"])

    def _stream(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> Iterator[ChatGenerationChunk]:
        """
        The same generation, yielded token by token. `.stream(...)` arrives here.

        Total time is unchanged -- this is the same decode either way. What changes is when
        the first token is visible: about two seconds instead of the thirty it takes to
        finish 512 of them. On a local 3B model that difference is most of what "fast"
        means to somebody waiting.

        Deliberately no `response_schema` handling. Grammar-constrained JSON is only useful
        once it is complete and parsed, so the judge and the resource generators call
        `_generate` and there is nothing to gain by streaming a half-written object.
        """
        llama = _load_llama(self.gguf_path, self.n_ctx, self.n_threads,
                            self.n_gpu_layers, self.chat_format)

        params: Dict[str, Any] = {
            "messages": _to_payload(messages),
            "max_tokens": kwargs.get("max_tokens", self.max_tokens),
            "temperature": kwargs.get("temperature", self.temperature),
            "stream": True,
        }
        if stop:
            params["stop"] = stop

        for piece in llama.create_chat_completion(**params):
            # The opening chunk of an OpenAI-style stream carries only the role, and the
            # closing one only a finish_reason; both have no "content" key at all.
            token = (piece["choices"][0].get("delta") or {}).get("content")
            if not token:
                continue

            chunk = ChatGenerationChunk(message=AIMessageChunk(content=token))
            # Feeds LangChain's own callback handlers. Separate from this project's
            # on_token plumbing, which the chat agent drives itself.
            if run_manager:
                run_manager.on_llm_new_token(token, chunk=chunk)
            yield chunk
