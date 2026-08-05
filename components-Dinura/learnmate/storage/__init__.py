"""
Persistence: two databases, each in its own container with its own named volume.

    MongoDB (learnmate-mongo, :27018)   everything that is not a vector
    Qdrant  (learnmate-qdrant, :6335)   the chunk embeddings

`docker compose up -d` starts both. `docker compose down` keeps the data; only
`down -v` clears it.

The split is deliberate and asymmetric. MongoDB holds the PDFs (GridFS), the cleaned page
text, session bindings, chat history, generated resources and the evaluation log -- none
of which can be derived from anything else, so losing it loses the corpus. The vectors are
computed *from* that page text, so losing Qdrant only costs a re-ingest. That is why the
vector backend is swappable and MongoDB is not.

What is stored, per session kind:

    a chat session      sessions + chat_turns + the chunks it retrieves from
    a resource session  sessions + pages (read whole) + resources + evaluations

Both kinds point at the same document record, so one PDF serves both without being
embedded twice.

Where things live, in reading order:

    mongo.py           the connection, and StorageUnavailable
    indexes.py         every index the queries depend on, including the three unique ones
    ids.py             ObjectId coercion, shared by every module that queries by id

    pdf_files.py       the PDF bytes, in GridFS
    documents.py       the document record: store, look up, resolve, delete
    pages.py           the cleaned page text a resource session reads
    pdf_store.py       facade over those three

    sessions.py        which PDF a session is about, and what it is for
    history.py         chat turns
    resources.py       generated resources, with their whole attempt trail
    evaluations.py     the verdict log and its statistics
    content_store.py   facade over those four

    vectors.py         picks the vector backend
    qdrant_vectors.py  a Qdrant server: real HNSW, filtering server-side
    mongo_vectors.py   the same interface over MongoDB, when a second service is not wanted
"""

from .content_store import (
    bind_session_document,
    clear_history,
    evaluation_stats,
    get_resource,
    get_session,
    list_resources,
    list_sessions,
    load_history,
    log_evaluation,
    save_resource,
    save_turn,
    session_doc_id,
    stage_counts,
    unbind_session,
)
from .mongo import StorageUnavailable, close, ensure_indexes, get_db, supports_vector_search
from .mongo_vectors import MongoVectorStore
from .pdf_store import (
    delete_document,
    export_pdf,
    find_by_hash,
    get_active_document,
    get_document,
    get_pages,
    get_pdf_bytes,
    list_documents,
    mark_ingested,
    read_source,
    resolve_document,
    store_pages,
    store_pdf,
)
from .qdrant_vectors import QdrantUnavailable, QdrantVectorStore
from .vectors import build_vector_store, get_vector_store, reset_vector_store

__all__ = [
    "MongoVectorStore",
    "QdrantUnavailable",
    "QdrantVectorStore",
    "StorageUnavailable",
    "bind_session_document",
    "build_vector_store",
    "clear_history",
    "close",
    "delete_document",
    "ensure_indexes",
    "evaluation_stats",
    "export_pdf",
    "find_by_hash",
    "get_active_document",
    "get_db",
    "get_document",
    "get_pages",
    "get_pdf_bytes",
    "get_resource",
    "get_session",
    "get_vector_store",
    "list_documents",
    "list_resources",
    "list_sessions",
    "load_history",
    "log_evaluation",
    "mark_ingested",
    "read_source",
    "reset_vector_store",
    "resolve_document",
    "save_resource",
    "save_turn",
    "session_doc_id",
    "stage_counts",
    "store_pages",
    "store_pdf",
    "supports_vector_search",
    "unbind_session",
]
