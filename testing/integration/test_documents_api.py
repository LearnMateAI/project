"""I-02 — document upload HTTP contract (service and queue mocked)."""

from unittest.mock import patch

from testing.integration.app_factory import bearer, client


def test_list_documents_401_without_token():
    res = client().get("/api/documents")
    assert res.status_code == 401


def test_upload_400_when_service_rejects_file():
    headers, _, _ = bearer()
    with patch(
        "app.routers.documents.service.upload",
        side_effect=ValueError("Only PDF files are allowed."),
    ):
        res = client().post(
            "/api/documents",
            headers=headers,
            files={"file": ("notes.txt", b"hello", "text/plain")},
            data={"subject": "General"},
        )
    assert res.status_code == 400
    assert "Only PDF" in res.json()["detail"]


def test_upload_202_returns_document_and_job_id():
    headers, _, _ = bearer()
    fake_doc = {
        "id": "507f1f77bcf86cd799439011",
        "filename": "act.pdf",
        "processing_status": "Uploaded",
    }
    fake_job = {"_id": "job-1", "status": "queued"}
    with patch("app.routers.documents.service.upload", return_value=fake_doc), patch(
        "app.routers.documents.enqueue", return_value=fake_job
    ):
        res = client().post(
            "/api/documents",
            headers=headers,
            files={"file": ("act.pdf", b"%PDF-fake", "application/pdf")},
            data={"subject": "Constitutional Law"},
        )
    assert res.status_code == 202
    body = res.json()
    assert body["job_id"] == "job-1"
    assert body["document"]["filename"] == "act.pdf"
    assert body["status"] == "queued"
