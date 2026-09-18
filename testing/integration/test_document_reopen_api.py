"""I-09 — reopening a past upload (`GET /api/documents/{id}`, `/file`, `/pages`).

Backs the "past uploads" library / dashboard reopen and the full-window PDF/text reader
(thevindu-feature). Service layer mocked; no Mongo, no GridFS.
"""

from unittest.mock import patch

from testing.integration.app_factory import bearer, client


def test_get_document_401_without_token():
    res = client().get("/api/documents/507f1f77bcf86cd799439011")
    assert res.status_code == 401


def test_get_document_404_when_not_owned():
    from app.errors import NotFound

    headers, _, _ = bearer()
    with patch("app.routers.documents.service.get_document",
               side_effect=NotFound("Document not found.")):
        res = client().get("/api/documents/507f1f77bcf86cd799439011", headers=headers)
    assert res.status_code == 404


def test_get_document_200_returns_metadata():
    headers, _, _ = bearer()
    fake_doc = {
        "id": "507f1f77bcf86cd799439011",
        "filename": "contract-act.pdf",
        "processing_status": "Ready",
        "source_kind": "pdf",
    }
    with patch("app.routers.documents.service.get_document", return_value=fake_doc):
        res = client().get("/api/documents/507f1f77bcf86cd799439011", headers=headers)
    assert res.status_code == 200
    assert res.json()["filename"] == "contract-act.pdf"


def test_get_document_file_401_without_token():
    res = client().get("/api/documents/507f1f77bcf86cd799439011/file")
    assert res.status_code == 401


def test_get_document_file_200_streams_bytes_inline_with_safe_filename():
    headers, _, _ = bearer()
    fake_doc = {"id": "507f1f77bcf86cd799439011", "filename": 'evil".pdf\r\nX-Injected: 1'}
    with patch("app.routers.documents.service.get_document", return_value=fake_doc), \
         patch("app.routers.documents.service.get_pdf_bytes", return_value=b"%PDF-fake-bytes"), \
         patch("app.routers.documents.service.get_file_media_type", return_value="application/pdf"):
        res = client().get("/api/documents/507f1f77bcf86cd799439011/file", headers=headers)
    assert res.status_code == 200
    assert res.content == b"%PDF-fake-bytes"
    disposition = res.headers["content-disposition"]
    assert disposition.startswith("inline;")
    assert "\r" not in disposition and "\n" not in disposition
    assert disposition == 'inline; filename="evil_.pdf__X-Injected_ 1"'


def test_get_document_pages_401_without_token():
    res = client().get("/api/documents/507f1f77bcf86cd799439011/pages")
    assert res.status_code == 401


def test_get_document_pages_200_returns_cleaned_text():
    headers, _, _ = bearer()
    fake_pages = [{"page_number": 1, "text": "Section 1. Directors owe duties."}]
    with patch("app.routers.documents.service.get_pages", return_value=fake_pages):
        res = client().get(
            "/api/documents/507f1f77bcf86cd799439011/pages?first=1&last=1", headers=headers
        )
    assert res.status_code == 200
    assert res.json() == fake_pages


def test_get_document_pages_422_on_non_positive_page_number():
    headers, _, _ = bearer()
    res = client().get(
        "/api/documents/507f1f77bcf86cd799439011/pages?first=0", headers=headers
    )
    assert res.status_code == 422
