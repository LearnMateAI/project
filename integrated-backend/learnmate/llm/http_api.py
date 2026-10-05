"""
Backend 2 of 2: a model served over an OpenAI-compatible HTTP API.

The path the finetuned model takes if it ends up behind local-model-api/ or
finetuned-model-api/ instead of shipping as a GGUF. Switching to it is a change to
LEARNMATE_GENERATOR_BACKEND and nothing else -- the agents never learn which backend
answered them.

It is also the scaling path. llama.cpp's own `llama-server` with `--parallel N` serves N
requests at once and batches their tokens into shared forward passes (continuous
batching), so a pool of job workers (app/jobs/worker.py) talking to it gets real
concurrency where the in-process backend can only take turns. scripts/serve/ starts one
for each role.
"""

import json
import os
import threading
from typing import Any, Dict, Iterator, List, Optional

from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessageChunk, BaseMessage
from langchain_core.outputs import ChatGenerationChunk, ChatResult

from .messages import _as_result, _to_payload

# HTTP statuses that mean "this server does not accept that request shape" -- the only
# reason to retry without the JSON schema. A timeout or a 5xx is the server being slow or
# broken, and asking it the same question again unconstrained would double the wait and
# then hand the parser free text.
_SCHEMA_REJECTED = {400, 415, 422, 501}

# One connection pool per thread: requests.Session is not documented as thread-safe, and a
# worker pool keeps several requests to the same server in flight. Reusing the connection
# saves a TCP handshake per call, which matters when a turn makes three of them.
_SESSIONS = threading.local()


def _session():
    import requests  # lazy, like llama_cpp: neither backend forces the other's deps

    session = getattr(_SESSIONS, "session", None)
    if session is None:
        session = requests.Session()
        _SESSIONS.session = session
    return session


class HttpChatModel(BaseChatModel):
    """
    An OpenAI-compatible chat endpoint, for when the model is served rather than loaded.

    `response_schema` is forwarded as OpenAI-style `response_format` (llama-server reads
    it as a grammar, exactly like the in-process backend); a server that rejects the shape
    gets a plain retry, so an endpoint without schema support still works.
    """

    base_url: str
    model_name: str = "local-model"
    api_key: Optional[str] = None
    temperature: float = 0.3
    max_tokens: int = 512
    # Generous by design: a 3B model on CPU behind a local server can take minutes for a
    # long resource, and a timeout here reads as a failed generation.
    timeout: int = int(os.getenv("LEARNMATE_HTTP_TIMEOUT_S") or 300)

    @property
    def _llm_type(self) -> str:
        return "learnmate-http"

    @property
    def _identifying_params(self) -> Dict[str, Any]:
        return {"base_url": self.base_url, "model_name": self.model_name}

    def _headers(self, stream: bool = False) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if stream:
            headers["Accept"] = "text/event-stream"
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _post(self, body: Dict[str, Any]) -> str:
        """One POST to /chat/completions, returning just the reply text."""
        response = _session().post(f"{self.base_url.rstrip('/')}/chat/completions",
                                   json=body, headers=self._headers(),
                                   timeout=self.timeout)
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        """Same contract as the llama.cpp backend, over the network instead."""
        body: Dict[str, Any] = {
            "model": self.model_name,
            "messages": _to_payload(messages),
            "max_tokens": kwargs.get("max_tokens", self.max_tokens),
            "temperature": kwargs.get("temperature", self.temperature),
        }
        if stop:
            body["stop"] = stop

        # The served equivalent of llama.cpp's grammar: a json_schema response_format.
        # Not every server implements it, so a rejection of the *shape* falls back to asking
        # plainly rather than failing the generation. Nothing else does -- see
        # _SCHEMA_REJECTED.
        schema = kwargs.get("response_schema")
        if schema is not None:
            import requests

            constrained = dict(body)
            constrained["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": "response", "schema": schema, "strict": True},
            }
            try:
                return _as_result(self._post(constrained))
            except requests.HTTPError as exc:
                status = getattr(exc.response, "status_code", None)
                if status not in _SCHEMA_REJECTED:
                    raise

        return _as_result(self._post(body))

    def _stream(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> Iterator[ChatGenerationChunk]:
        """
        Server-sent events from `/chat/completions`, one chunk per token.

        The same contract as the llama.cpp backend's `_stream`, so the chat agent cannot
        tell which one answered -- which is the whole point of having two backends behind
        one interface. llama-server, vLLM and anything else OpenAI-compatible all speak
        this format.
        """
        body: Dict[str, Any] = {
            "model": self.model_name,
            "messages": _to_payload(messages),
            "max_tokens": kwargs.get("max_tokens", self.max_tokens),
            "temperature": kwargs.get("temperature", self.temperature),
            "stream": True,
        }
        if stop:
            body["stop"] = stop

        with _session().post(f"{self.base_url.rstrip('/')}/chat/completions",
                             json=body, headers=self._headers(stream=True),
                             timeout=self.timeout, stream=True) as response:
            response.raise_for_status()

            for line in response.iter_lines(decode_unicode=True):
                # Keep-alive blanks and any comment line the server sends between events.
                if not line or not line.startswith("data:"):
                    continue

                payload = line[len("data:"):].strip()
                if payload == "[DONE]":
                    break

                try:
                    piece = json.loads(payload)
                except ValueError:
                    # A malformed frame is one lost token, not a lost answer.
                    continue

                choices = piece.get("choices") or [{}]
                token = (choices[0].get("delta") or {}).get("content")
                if not token:
                    continue

                chunk = ChatGenerationChunk(message=AIMessageChunk(content=token))
                if run_manager:
                    run_manager.on_llm_new_token(token, chunk=chunk)
                yield chunk
