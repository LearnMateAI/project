"""
Small shared utilities used by more than one node.

Nothing here makes a decision -- these only format and print.
"""

from typing import Dict, List

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

from .state import ChatState


def _log(state: ChatState, message: str) -> None:
    """
    Print progress, unless the caller asked for silence.

    Defaults to on: the CLI wants the running commentary, and a caller embedding the
    agent in a server passes verbose=False once at construction.
    """
    if state.get("verbose", True):
        print(message)


def _as_messages(history: List[Dict[str, str]]) -> List[BaseMessage]:
    """
    Convert stored history into LangChain message objects.

    History is persisted as plain dicts so it stays readable in MongoDB, but the chat
    models want typed messages. Anything not explicitly tagged "assistant" is treated as
    a user turn, so an unknown or missing role degrades to the safe interpretation
    rather than raising mid-conversation.
    """
    messages: List[BaseMessage] = []
    for turn in history or []:
        if turn.get("role") == "assistant":
            messages.append(AIMessage(content=turn.get("content", "")))
        else:
            messages.append(HumanMessage(content=turn.get("content", "")))
    return messages
