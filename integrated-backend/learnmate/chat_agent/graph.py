"""
Wiring: the nodes assembled into a LangGraph state machine.

This file contains no logic of its own -- it only says how the pieces connect. The
behaviour lives in the node modules it imports.

    rewrite -> retrieve -> generate -> evaluate -> decide -+-> persist -> END
                              ^                            |
                              +--------- regenerate -------+

Only one edge is conditional (evaluate -> decide). Everything else is a straight line,
which is deliberate: the sequencing is fixed and only the accept/retry choice depends on
what happened at runtime.
"""

from langgraph.graph import END, StateGraph

from .evaluate import evaluate_node
from .generate import generate_node
from .persist import persist_node
from .retrieve import retrieve_node
from .rewrite import rewrite_node
from .routing import decide
from .state import ChatState


def build_chat_graph():
    """Compile the one-turn chat graph."""
    # The state schema tells LangGraph which keys exist and which ones have reducers.
    graph = StateGraph(ChatState)

    graph.add_node("rewrite", rewrite_node)
    graph.add_node("retrieve", retrieve_node)
    graph.add_node("generate", generate_node)
    graph.add_node("evaluate", evaluate_node)
    graph.add_node("persist", persist_node)

    graph.set_entry_point("rewrite")
    graph.add_edge("rewrite", "retrieve")
    graph.add_edge("retrieve", "generate")
    graph.add_edge("generate", "evaluate")

    # `decide` returns "generate" or "persist"; this mapping turns those strings into
    # the actual edges. The "generate" branch is what closes the retry loop.
    graph.add_conditional_edges("evaluate", decide,
                                {"generate": "generate", "persist": "persist"})

    graph.add_edge("persist", END)
    return graph.compile()


# Compiling is cheap but not free, and the graph is stateless once built -- every turn
# passes its own state in -- so one process-wide instance is safe and saves the work on
# every message after the first.
_GRAPH = None


def get_chat_graph():
    """Process-wide compiled graph, built on first use."""
    global _GRAPH
    if _GRAPH is None:
        _GRAPH = build_chat_graph()
    return _GRAPH
