"""
LearnMate: a local, MongoDB-backed study assistant.

Three agents over one corpus:

    chat_agent      answers questions about an ingested PDF, or from general knowledge
                    when nothing relevant is retrieved
    resource_agent  generates MCQs, practice questions, key points and summaries from a
                    document's text
    evaluator       grades what the other two produce and drives a single retry

Both agents are LangGraph state machines over LangChain components. Everything persists
to an external MongoDB: the PDFs themselves in GridFS, their chunk vectors, the generated
resources and the evaluation log.

Typical use:

    from learnmate import ChatAgent, generate_resource, ingest_pdf

    report = ingest_pdf("notes.pdf")
    agent = ChatAgent(doc_id=report["doc_id"])
    print(agent.ask("What are the directors' duties?")["reply"])

    result = generate_resource("mcq", source_text, count=5, doc_id=report["doc_id"])
"""

from . import config
from .chat_agent import ChatAgent
from .evaluator import Judge, get_judge
from .ingestion import build_source_text, ingest_pdf
from .resource_agent import TASK_NAMES, generate_resource, render

__all__ = [
    "ChatAgent",
    "Judge",
    "TASK_NAMES",
    "build_source_text",
    "config",
    "generate_resource",
    "get_judge",
    "ingest_pdf",
    "render",
]

__version__ = "1.0.0"
