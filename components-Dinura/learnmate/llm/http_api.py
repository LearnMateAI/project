"""
Backend 2 of 2: a model served over an OpenAI-compatible HTTP API.

The path the finetuned model takes if it ends up behind local-model-api/ or
finetuned-model-api/ instead of shipping as a GGUF. Switching to it is a change to
LEARNMATE_GENERATOR_BACKEND and nothing else -- the agents never learn which backend
answered them.
"""

from typing import Any, Dict, List, Optional

from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage
from langchain_core.outputs import ChatResult

from .messages import _as_result, _to_payload


class HttpChatModel(BaseChatModel):
    """
    An OpenAI-compatible chat endpoint, for when the model is served rather than loaded.

    `response_schema` is forwarded as OpenAI-style `response_format`; servers that reject
    it get a plain retry, so an endpoint without schema support still works.
    """

    base_url: str
    model_name: str = "local-model"
    api_key: Optional[str] = None
    temperature: float = 0.3
    max_tokens: int = 512
    # Generous by design: a 3B model on CPU behind a local server can take minutes for a
    # long resource, and a timeout here reads as a failed generation.
    timeout: int = 300

    @property
    def _llm_type(self) -> str:
        return "learnmate-http"

    @property
    def _identifying_params(self) -> Dict[str, Any]:
        return {"base_url": self.base_url, "model_name": self.model_name}

    def _post(self, body: Dict[str, Any]) -> str:
        """One POST to /chat/completions, returning just the reply text."""
        import requests  # lazy, like llama_cpp: neither backend forces the other's deps

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
        # Not every server implements it, so a rejection falls back to asking plainly
        # rather than failing the generation.
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
