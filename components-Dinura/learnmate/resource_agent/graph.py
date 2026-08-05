"""
Wiring: the nodes assembled into a LangGraph state machine.

    generate -> check -> decide -+-> persist -> END
        ^                        |
        +------ regenerate ------+

No logic of its own -- only how the pieces connect. `decide` is the single place the loop
can end.

Expressing this as a graph rather than a for-loop is what makes the flow inspectable:
every node's decision lands in the state, so a run that produced bad output can be read
back afterwards instead of guessed at.
"""

from langgraph.graph import END, StateGraph

from .check import check_node
from .generate import generate_node
from .persist import persist_node
from .routing import decide
from .state import ResourceState


def build_resource_graph():
    """Compile the generate/check/retry graph."""
    graph = StateGraph(ResourceState)
    graph.add_node("generate", generate_node)
    graph.add_node("check", check_node)
    graph.add_node("persist", persist_node)

    graph.set_entry_point("generate")
    graph.add_edge("generate", "check")

    # `decide` returns "generate" or "persist"; this mapping turns those strings into the
    # actual edges. The "generate" branch is what closes the retry loop.
    graph.add_conditional_edges("check", decide,
                                {"generate": "generate", "persist": "persist"})

    graph.add_edge("persist", END)
    return graph.compile()


# Compiled once and reused: the graph is stateless, every run passes its own state in.
_GRAPH = None


def get_resource_graph():
    """Process-wide compiled graph, built on first use."""
    global _GRAPH
    if _GRAPH is None:
        _GRAPH = build_resource_graph()
    return _GRAPH
