"""U-15 — engine exceptions become HTTP status codes (`app/errors.py`)."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.errors import AccessDenied, NotFound, register_error_handlers
from learnmate.storage.mongo import StorageUnavailable
from learnmate.storage.qdrant_vectors import QdrantUnavailable


def _app():
    app = FastAPI()
    register_error_handlers(app)

    @app.get("/value")
    def _value():
        raise ValueError("This PDF is password-protected. Please upload an unprotected copy.")

    @app.get("/missing")
    def _missing():
        raise NotFound("Document not found.")

    @app.get("/denied")
    def _denied():
        raise AccessDenied("Not in your library.")

    @app.get("/mongo")
    def _mongo():
        raise StorageUnavailable("mongodb://localhost:27018")

    @app.get("/qdrant")
    def _qdrant():
        raise QdrantUnavailable("http://localhost:6335")

    @app.get("/boom")
    def _boom():
        raise RuntimeError("stack should not leak")

    return app


def test_value_error_is_400_with_engine_message():
    client = TestClient(_app(), raise_server_exceptions=False)
    res = client.get("/value")
    assert res.status_code == 400
    assert "password-protected" in res.json()["detail"]


def test_not_found_is_404():
    res = TestClient(_app(), raise_server_exceptions=False).get("/missing")
    assert res.status_code == 404
    assert res.json()["detail"] == "Document not found."


def test_access_denied_is_403():
    res = TestClient(_app(), raise_server_exceptions=False).get("/denied")
    assert res.status_code == 403


def test_storage_down_is_503():
    res = TestClient(_app(), raise_server_exceptions=False).get("/mongo")
    assert res.status_code == 503


def test_qdrant_down_is_503():
    res = TestClient(_app(), raise_server_exceptions=False).get("/qdrant")
    assert res.status_code == 503


def test_unhandled_is_500_without_traceback_in_body():
    res = TestClient(_app(), raise_server_exceptions=False).get("/boom")
    assert res.status_code == 500
    assert "stack should not leak" not in res.text
    assert "Please try again" in res.json()["detail"]
