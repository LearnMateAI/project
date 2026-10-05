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

With LEARNMATE_CACHE_ENABLED the answer cache adds a second conditional edge, and one node
at each end (see cache_nodes.py):

    rewrite -> cache_lookup -+-> retrieve -> generate -> ... -> persist -> cache_store -> END
                             +-> persist (hit) ---------------------^
"""

from langgraph.graph import END, StateGraph

from .. import config
from .cache_nodes import cache_lookup_node, cache_store_node, route_after_cache
from .evaluate import evaluate_node
from .generate import generate_node
from .persist import persist_node
from .retrieve import retrieve_node
from .rewrite import rewrite_node
from .routing import decide
from .state import ChatState


def build_chat_graph(with_cache: bool = None):
    """Compile the one-turn chat graph."""
    with_cache = config.CACHE_ENABLED if with_cache is None else with_cache
    # The state schema tells LangGraph which keys exist and which ones have reducers.
    graph = StateGraph(ChatState)

    graph.add_node("rewrite", rewrite_node)
    graph.add_node("retrieve", retrieve_node)
    graph.add_node("generate", generate_node)
    graph.add_node("evaluate", evaluate_node)
    graph.add_node("persist", persist_node)

    graph.set_entry_point("rewrite")
    if with_cache:
        graph.add_node("cache_lookup", cache_lookup_node)
        graph.add_node("cache_store", cache_store_node)
        graph.add_edge("rewrite", "cache_lookup")
        graph.add_conditional_edges("cache_lookup", route_after_cache,
                                    {"persist": "persist", "retrieve": "retrieve"})
    else:
        graph.add_edge("rewrite", "retrieve")
    graph.add_edge("retrieve", "generate")
    graph.add_edge("generate", "evaluate")

    # `decide` returns "generate" or "persist"; this mapping turns those strings into
    # the actual edges. The "generate" branch is what closes the retry loop.
    graph.add_conditional_edges("evaluate", decide,
                                {"generate": "generate", "persist": "persist"})

    if with_cache:
        graph.add_edge("persist", "cache_store")
        graph.add_edge("cache_store", END)
    else:
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
