"""
Backend 3 of 3: Google's Gemini API.

The cloud path. Everything else in this package runs a 3B model on the CPU, which is
private and free but takes ~30 seconds to answer a question and minutes to write a
question set; Gemini answers in a second or two. Which one is in use is
LEARNMATE_GENERATOR_BACKEND and nothing else -- the agents, both graphs, the evaluator and
the retry loop never learn which backend replied.

Shaped exactly like http_api.py, because the differences from an OpenAI-compatible
endpoint are only three and all of them are handled here:

    the system prompt is a separate `system_instruction`, not a message with role=system
    the assistant role is called "model", not "assistant"
    a JSON schema is `response_schema` on the config, not a `response_format` on the body

`google.genai` is imported lazily, like llama_cpp and requests, so a deployment that never
uses this backend does not need the package installed.
"""

from typing import Any, Dict, List, Optional

from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage
from langchain_core.outputs import ChatResult

from .messages import _as_result, _to_payload

# Gemini rejects the JSON Schema keywords llama.cpp's grammar compiler is happy to ignore.
# Stripping them is what lets one schema serve all three backends -- see _clean_schema.
_UNSUPPORTED_SCHEMA_KEYS = (
    "additionalProperties", "$schema", "definitions", "$defs", "title", "default",
    "examples", "const", "pattern", "minLength", "maxLength", "uniqueItems",
)


def _clean_schema(schema: Any) -> Any:
    """
    Strip the schema keywords Gemini's subset of JSON Schema rejects.

    The task schemas in resource_agent/ and the verdict schema in evaluator/ are written
    for llama.cpp's grammar compiler, which accepts full JSON Schema. Gemini errors on
    anything outside its subset rather than ignoring it, so the same schema would fail
    here for reasons that have nothing to do with the content being generated.
    """
    if isinstance(schema, dict):
        return {key: _clean_schema(value) for key, value in schema.items()
                if key not in _UNSUPPORTED_SCHEMA_KEYS}
    if isinstance(schema, list):
        return [_clean_schema(item) for item in schema]
    return schema


def _split_messages(messages: List[BaseMessage]):
    """
    Split LangChain messages into (system_instruction, contents).

    Gemini takes the system prompt out of band, so system messages are pulled out and
    joined; everything else becomes a turn with Gemini's role names.
    """
    system_parts, contents = [], []

    for message in _to_payload(messages):
        role, text = message["role"], message["content"]
        if role == "system":
            system_parts.append(text)
            continue
        # Gemini calls the assistant "model". Everything else is a user turn, which is the
        # reading that cannot confuse the model into thinking it wrote the text itself.
        contents.append({
            "role": "model" if role == "assistant" else "user",
            "parts": [{"text": text}],
        })

    # A conversation with no user turn at all is not a thing Gemini will answer; this only
    # happens if a caller passes a lone system message, and an empty prompt is clearer
    # than an API error about `contents`.
    if not contents:
        contents = [{"role": "user", "parts": [{"text": ""}]}]

    return "\n\n".join(system_parts), contents


class GeminiChatModel(BaseChatModel):
    """
    A Gemini model behind the same BaseChatModel surface as the two local backends.

    `response_schema` is forwarded as structured-output config; a model or schema that
    rejects it falls back to asking plainly, exactly as the other backends do, because
    parse_json_reply recovers JSON from a fenced or prefaced reply.
    """

    api_key: str
    model_name: str = "gemini-2.0-flash"
    temperature: float = 0.3
    max_tokens: int = 512

    @property
    def _llm_type(self) -> str:
        return "learnmate-gemini"

    @property
    def _identifying_params(self) -> Dict[str, Any]:
        return {"model_name": self.model_name}

    def _client(self):
        from google import genai  # lazy: this backend is optional

        return genai.Client(api_key=self.api_key)

    def _call(self, messages: List[BaseMessage], stop, schema, temperature, max_tokens
              ) -> str:
        """One request, returning just the reply text."""
        from google.genai import types

        system_instruction, contents = _split_messages(messages)

        settings: Dict[str, Any] = {
            "temperature": temperature,
            "max_output_tokens": max_tokens,
        }
        if system_instruction:
            settings["system_instruction"] = system_instruction
        if stop:
            settings["stop_sequences"] = list(stop)
        if schema is not None:
            settings["response_mime_type"] = "application/json"
            settings["response_schema"] = _clean_schema(schema)

        response = self._client().models.generate_content(
            model=self.model_name,
            contents=contents,
            config=types.GenerateContentConfig(**settings),
        )
        # A response blocked by a safety filter has no `.text`; treat it as an empty
        # generation so the caller's retry loop handles it like any other bad attempt.
        return (response.text or "") if hasattr(response, "text") else ""

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        """Same contract as the llama.cpp and HTTP backends, against the Gemini API."""
        temperature = kwargs.get("temperature", self.temperature)
        max_tokens = kwargs.get("max_tokens", self.max_tokens)
        schema = kwargs.get("response_schema")

        if schema is not None:
            try:
                return _as_result(
                    self._call(messages, stop, schema, temperature, max_tokens))
            except Exception:
                # Structured output refused (an unsupported schema, an older model). Ask
                # plainly instead of failing the attempt; json_output.parse_json_reply is
                # written for exactly this reply.
                pass

        return _as_result(self._call(messages, stop, None, temperature, max_tokens))
