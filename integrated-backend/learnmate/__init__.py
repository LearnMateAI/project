"""
LearnMate: a local study assistant over your own PDFs.

Three agents over one corpus:

    chat_agent      answers questions about an ingested PDF, or from general knowledge
                    when nothing relevant is retrieved
    resource_agent  generates MCQs, practice questions, key points and summaries from a
                    document's text
    evaluator       grades what the other two produce and drives a single retry

Both agents are LangGraph state machines over LangChain components, and both run entirely
on local models: Qwen2.5-3B generates, Llama-3.2-3B judges, MiniLM embeds.

Two databases, each in its own container (`docker compose up -d`):

    MongoDB (:27018)  the PDFs in GridFS, their cleaned page text, session bindings,
                      chat history, generated resources and the evaluation log
    Qdrant  (:6335)   the chunk embeddings

The asymmetry is deliberate. Nothing in MongoDB can be derived from anything else, so
losing it loses the corpus; the vectors are computed from that page text, so losing Qdrant
only costs a re-ingest. That is why the vector backend is swappable
(LEARNMATE_VECTOR_BACKEND=mongodb keeps everything in one service) and MongoDB is not.

An upload belongs to a session, and a session is about exactly one PDF, opened either for
chat or for resource generation.

Typical use:

    from learnmate import ChatAgent, build_source_text, generate_resource, ingest_pdf

    report = ingest_pdf("notes.pdf", session_id="s1", session_for="both")
    doc_id = report["doc_id"]

    agent = ChatAgent(session_id="s1", doc_id=doc_id)
    print(agent.ask("What are the directors' duties?")["reply"])

    source = build_source_text(doc_id, topic="directors' duties")
    result = generate_resource("mcq", source, count=5, doc_id=doc_id)
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
