"""
Every index the queries in this package depend on.

Created once on first connect. All of them are idempotent, so calling ensure_indexes()
repeatedly is free -- which is what lets get_db() call it unconditionally.

Five of them are `unique`, and each enforces a rule the rest of the system relies on
rather than merely making a query fast:

    documents.sha256                      one document per set of bytes, so re-uploading
                                          the same PDF is recognised instead of duplicated
    chunks.(doc_id, page, chunk_index)    re-ingesting overwrites a chunk in place
    sessions.session_id                   one PDF per session, structurally
    users.email                           one account per address
    user_documents.(user_id, doc_id)      one library entry per user per document
"""

from pymongo import ASCENDING, DESCENDING
from pymongo.database import Database

from .. import config


def create_indexes(database: Database) -> None:
    """Create every index, idempotently."""
    # --- PDFs and their derived text --------------------------------------------------
    # sha256 unique is what makes "store once, retrieve quickly" hold across sessions.
    database[config.COLL_DOCUMENTS].create_index([("sha256", ASCENDING)], unique=True)
    # get_active_document() and list_documents() both read newest-first.
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

    # --- Generated content and its audit trail ----------------------------------------
    database[config.COLL_RESOURCES].create_index(
        [("doc_id", ASCENDING), ("task", ASCENDING), ("created_at", DESCENDING)])
    # Every listing in the API is "this user's resources, newest first".
    database[config.COLL_RESOURCES].create_index(
        [("user_id", ASCENDING), ("created_at", DESCENDING)])
    database[config.COLL_EVALUATIONS].create_index([("created_at", DESCENDING)])
    database[config.COLL_EVALUATIONS].create_index([("task", ASCENDING)])
    database[config.COLL_EVALUATIONS].create_index([("user_id", ASCENDING)])

    # --- Sessions ---------------------------------------------------------------------
    # load_history reads the newest N turns of one session; this index makes that a
    # bounded scan rather than a sort of the whole collection.
    database[config.COLL_CHAT_TURNS].create_index(
        [("session_id", ASCENDING), ("created_at", ASCENDING)])
    database[config.COLL_CHAT_TURNS].create_index([("user_id", ASCENDING)])

    # One record per session. Unique because the binding is what enforces one PDF per
    # session -- two records for the same id would mean two answers to "which document
    # is this session about".
    database[config.COLL_SESSIONS].create_index([("session_id", ASCENDING)], unique=True)
    database[config.COLL_SESSIONS].create_index(
        [("user_id", ASCENDING), ("bound_at", DESCENDING)])

    # --- Accounts and who may see what ------------------------------------------------
    # Unique because an account is identified by its address; the register path relies on
    # the DuplicateKeyError this raises rather than checking first and racing.
    database[config.COLL_USERS].create_index([("email", ASCENDING)], unique=True)

    # The library: one row per (user, document). Unique so uploading the same PDF twice
    # refreshes the entry instead of listing it twice, and indexed on user_id because
    # "list my documents" is the most frequent query in the whole API.
    database[config.COLL_USER_DOCUMENTS].create_index(
        [("user_id", ASCENDING), ("doc_id", ASCENDING)], unique=True)
    database[config.COLL_USER_DOCUMENTS].create_index(
        [("user_id", ASCENDING), ("added_at", DESCENDING)])
    # Deleting asks "does anyone else still have this document?", which is a count by
    # doc_id alone.
    database[config.COLL_USER_DOCUMENTS].create_index([("doc_id", ASCENDING)])

    # --- Background jobs --------------------------------------------------------------
    database[config.COLL_JOBS].create_index(
        [("user_id", ASCENDING), ("created_at", DESCENDING)])
    database[config.COLL_JOBS].create_index([("status", ASCENDING)])
