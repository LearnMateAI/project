"""
Translation between LangChain's message objects and the wire format both backends use.

llama.cpp and an OpenAI-compatible HTTP API want the same thing -- a list of
`{"role": ..., "content": ...}` dicts -- so this conversion is shared rather than written
twice. Keeping it here is also what lets the two backend classes stay short enough to read
in one sitting.
"""

from typing import Dict, List

from langchain_core.messages import AIMessage, BaseMessage, ChatMessage
from langchain_core.outputs import ChatGeneration, ChatResult


def _to_payload(messages: List[BaseMessage]) -> List[Dict[str, str]]:
    """
    Convert LangChain messages into the role/content dicts both backends expect.

    LangChain names the roles differently from the chat-completions API ("human" rather
    than "user", "ai" rather than "assistant"), so they are mapped rather than passed
    through. A ChatMessage carries an explicit role and keeps it. Anything unrecognised
    falls back to "user", which is the interpretation that cannot confuse a model into
    thinking it wrote the text itself.
    """
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
    """
    Wrap generated text in the ChatResult a BaseChatModel must return.

    Both backends produce a single completion, so the generations list always has exactly
    one entry -- there is no n>1 sampling anywhere in this project.
    """
    return ChatResult(generations=[ChatGeneration(message=AIMessage(content=text or ""))])
