"""
Engine exceptions to HTTP status codes, in one place.

The services below this layer raise plain Python exceptions and never import FastAPI. That
keeps them callable from the job worker, where there is no request to fail -- but it means
something has to decide that an unreachable Qdrant is a 503 and a PDF with no text layer is
a 400. This is that something, registered once on the app.

Three exceptions carry the interesting cases:

    StorageUnavailable  MongoDB is down          503, with the URI that was tried
    QdrantUnavailable   the vector store is down 503, with the URL that was tried
    ValueError          the request cannot work  400, with the engine's own message

The last one matters more than it looks. The engine's ValueError messages are already
written for a person -- "Session 's1' was opened for chat, not resource generation", "No
extractable text in notes.pdf. If it is a scanned PDF it needs OCR" -- so they are passed
through unchanged rather than replaced with something vaguer.

Anything else is a bug, and becomes a 500 with the traceback in the server log and nothing
revealing in the response.
"""

import logging
import traceback

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from learnmate.storage.mongo import StorageUnavailable
from learnmate.storage.qdrant_vectors import QdrantUnavailable

logger = logging.getLogger("learnmate.api")


class AccessDenied(Exception):
    """
    Raised by a service when the caller may not touch the thing they named.

    A separate exception rather than an HTTPException so services stay importable from
    the job worker, which has no request to fail.
    """


class NotFound(Exception):
    """Raised by a service when the thing the caller named does not exist."""


def register_error_handlers(app: FastAPI) -> None:
    """Attach every handler. Called once from server.py."""

    @app.exception_handler(StorageUnavailable)
    async def _storage_unavailable(request: Request, exc: StorageUnavailable):
        logger.error("MongoDB unavailable: %s", exc)
        return JSONResponse(status_code=503, content={"detail": str(exc)})

    @app.exception_handler(QdrantUnavailable)
    async def _qdrant_unavailable(request: Request, exc: QdrantUnavailable):
        logger.error("Qdrant unavailable: %s", exc)
        return JSONResponse(status_code=503, content={"detail": str(exc)})

    @app.exception_handler(NotFound)
    async def _not_found(request: Request, exc: NotFound):
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(AccessDenied)
    async def _access_denied(request: Request, exc: AccessDenied):
        return JSONResponse(status_code=403, content={"detail": str(exc)})

    @app.exception_handler(ValueError)
    async def _bad_request(request: Request, exc: ValueError):
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception):
        # Logged in full, reported vaguely: a stack trace in an HTTP response tells an
        # attacker about the inside of the system and tells the user nothing useful.
        logger.error("Unhandled error on %s %s\n%s", request.method, request.url.path,
                     traceback.format_exc())
        return JSONResponse(
            status_code=500,
            content={"detail": "Something went wrong on the server. Please try again."},
        )
