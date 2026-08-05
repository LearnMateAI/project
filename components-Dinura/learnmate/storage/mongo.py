"""
MongoDB connection and schema setup.

One external server holds everything the system persists: the uploaded PDFs (GridFS),
their text chunks and embeddings, the generated resources, the evaluation log and the
chat history. Nothing is written to local disk, so any process on any machine that can
reach the URI sees the same corpus.

Indexes are created once on first connect. All of them are idempotent, so calling
ensure_indexes() repeatedly is free.
"""

from typing import Optional

from pymongo import ASCENDING, DESCENDING, MongoClient
from pymongo.database import Database
from pymongo.errors import PyMongoError, ServerSelectionTimeoutError

from .. import config

_CLIENT: Optional[MongoClient] = None
_INDEXES_READY = False


class StorageUnavailable(RuntimeError):
    """Raised when MongoDB cannot be reached, with the URI that was tried."""


def get_client() -> MongoClient:
    """Connect to MongoDB, verifying the server is actually reachable."""
    global _CLIENT
    if _CLIENT is None:
        client = MongoClient(config.MONGODB_URI, serverSelectionTimeoutMS=5000)
        try:
            # MongoClient is lazy; ping so a bad URI fails here with a clear message
            # rather than deep inside an unrelated query later.
            client.admin.command("ping")
        except ServerSelectionTimeoutError as exc:
            raise StorageUnavailable(
                f"Cannot reach MongoDB at {config.MONGODB_URI}. Start the server or set "
                f"LEARNMATE_MONGODB_URI. Original error: {exc}"
            ) from exc
        _CLIENT = client
    return _CLIENT


def get_db() -> Database:
    """The LearnMate database, with indexes ensured on first use."""
    database = get_client()[config.MONGODB_DB]
    ensure_indexes(database)
    return database


def ensure_indexes(database: Database = None) -> None:
    """Create the indexes the queries in this package depend on."""
    global _INDEXES_READY
    if _INDEXES_READY:
        return

    database = database if database is not None else get_client()[config.MONGODB_DB]

    # sha256 is unique so re-uploading the same PDF is detected instead of duplicated;
    # it is what makes "store once, retrieve quickly" hold across sessions.
    database[config.COLL_DOCUMENTS].create_index([("sha256", ASCENDING)], unique=True)
    database[config.COLL_DOCUMENTS].create_index([("uploaded_at", DESCENDING)])

    # Retrieval always filters by document, and re-ingesting must overwrite a chunk
    # rather than append a second copy of it.
    database[config.COLL_CHUNKS].create_index([("doc_id", ASCENDING)])
    database[config.COLL_CHUNKS].create_index(
        [("doc_id", ASCENDING), ("page_number", ASCENDING), ("chunk_index", ASCENDING)],
        unique=True,
    )

    # Whole cleaned page text, kept alongside the chunks. Chunks overlap by design, so
    # joining them back together duplicates text at every boundary; resource generation
    # needs the page as it actually reads.
    database[config.COLL_PAGES].create_index(
        [("doc_id", ASCENDING), ("page_number", ASCENDING)], unique=True)

    database[config.COLL_RESOURCES].create_index(
        [("doc_id", ASCENDING), ("task", ASCENDING), ("created_at", DESCENDING)])
    database[config.COLL_EVALUATIONS].create_index([("created_at", DESCENDING)])
    database[config.COLL_EVALUATIONS].create_index([("task", ASCENDING)])
    database[config.COLL_CHAT_TURNS].create_index(
        [("session_id", ASCENDING), ("created_at", ASCENDING)])

    # One record per session. Unique because the binding is what enforces one PDF per
    # session -- two records for the same id would mean two answers to "which document
    # is this session about".
    database[config.COLL_SESSIONS].create_index([("session_id", ASCENDING)], unique=True)

    _INDEXES_READY = True


def supports_vector_search(database: Database = None) -> bool:
    """
    Whether the server can run $vectorSearch.

    Atlas exposes it through Atlas Search; a community server does not have it at any
    version. The answer decides whether MongoVectorStore pushes similarity down to the
    server or scores in NumPy, so it is checked rather than assumed.
    """
    database = database if database is not None else get_db()
    try:
        list(database[config.COLL_CHUNKS].list_search_indexes())
        return True
    except PyMongoError:
        return False


def close() -> None:
    """Drop the connection. Only needed by long-lived callers and tests."""
    global _CLIENT, _INDEXES_READY
    if _CLIENT is not None:
        _CLIENT.close()
        _CLIENT = None
        _INDEXES_READY = False
