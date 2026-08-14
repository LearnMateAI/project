"""
Small shared utilities used by more than one node.

Nothing here makes a decision -- these only format and print.
"""

from typing import Dict, List

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

from .state import ChatState


def _log(state: ChatState, message: str) -> None:
    """
    Report progress: to stdout unless silenced, and to `on_progress` when one is set.

    Defaults to printing: the CLI wants the running commentary. A caller embedding the
    agent in a server passes verbose=False and an on_progress callback instead, so the
    same messages reach a client polling a job record. The callback is never allowed to
    break the turn -- a failed progress update is cosmetic, a lost answer is not.
    """
    if state.get("verbose", True):
        print(message)

    report = state.get("on_progress")
    if report:
        try:
            report(message)
        except Exception:
            pass


def _emit_token(state: ChatState, text: str) -> None:
    """
    Hand the reply-so-far to whoever is streaming it.

    Called once per token, with the full accumulated text rather than the delta: the
    consumer stores a whole string anyway, and passing the accumulation means a dropped
    call costs nothing -- the next one carries everything the missed one would have.
    That is what lets the consumer throttle freely.

    Silenced like `_log`: a client that has gone away, or a slow write, must not be able
    to break the generation it is watching.
    """
    report = state.get("on_token")
    if not report:
        return
    try:
        report(text)
    except Exception:
        pass


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
