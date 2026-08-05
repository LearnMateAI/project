"""
The chat agent: retrieval-grounded PDF chat with a general-knowledge fallback.

One turn is one pass through a LangGraph state machine:

    rewrite -> retrieve -> generate -> evaluate -> decide -+-> persist -> END
                              ^                            |
                              +--------- regenerate -------+

Two possible modes, decided by retrieval rather than by asking the model:

    pdf mode      the top chunk scores at or above RELEVANCE_THRESHOLD, so the reply is
                  written from those chunks and judged strictly against them -- anything
                  they do not support is a hallucination
    general mode  nothing relevant was retrieved, so the reply comes from the model's own
                  knowledge and is judged only on relevance, coherence and informativeness

`rewrite` runs before retrieval, not after. A follow-up like "what about his powers?"
embeds to nothing useful; resolved against the history into "what are the President's
powers?" it retrieves correctly. Doing it in the other order retrieves on the pronoun.

The retry budget is one regeneration. The regenerated reply is returned whether or not it
clears the threshold -- a user mid-conversation needs an answer, and `accepted` reports
whether it was reviewed clean so a caller can flag it.

Where things live, in reading order:

    state.py      ChatState -- what flows between nodes, and the one reducer
    prompts.py    the three system prompts
    helpers.py    logging and history-to-messages conversion
    rewrite.py    node 1  resolve the follow-up into a standalone question
    retrieve.py   node 2  search the vectors, pick pdf or general mode
    generate.py   node 3  write the reply (re-entered on retry)
    evaluate.py   node 4  judge it, strictly if it was meant to be grounded
    routing.py            the accept-or-retry branch out of evaluate
    persist.py    node 5  save the turn to Mongo
    graph.py      the wiring that connects the above
    agent.py      ChatAgent -- the public entry point
"""

from .agent import ChatAgent
from .graph import build_chat_graph, get_chat_graph

__all__ = ["ChatAgent", "build_chat_graph", "get_chat_graph"]
