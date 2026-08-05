"""
The MongoDB connection.

One external server holds everything the system persists that is not a vector: the
uploaded PDFs (GridFS), their cleaned page text, session bindings, chat history, the
generated resources and the evaluation log. Nothing is written to local disk, so any
process that can reach the URI sees the same corpus.

It runs as this project's own container -- `docker compose up -d mongo`, published on
27018 with a named volume -- rather than a server shared with other projects. Losing this
database loses the corpus; losing the vector database only costs a re-ingest.

Indexes live next door in indexes.py and are created on first connect.
"""

from typing import Optional

from pymongo import MongoClient
from pymongo.database import Database
from pymongo.errors import PyMongoError, ServerSelectionTimeoutError

from .. import config
from .indexes import create_indexes

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
                f"Cannot reach MongoDB at {config.MONGODB_URI}. Start it with "
                f"`docker compose up -d mongo` (see docker-compose.yml), or set "
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
    """Create the indexes the queries in this package depend on, once per process."""
    global _INDEXES_READY
    if _INDEXES_READY:
        return

    database = database if database is not None else get_client()[config.MONGODB_DB]
    create_indexes(database)
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
