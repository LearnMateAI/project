"""I-03 — job polling contract (`app/routers/jobs.py`)."""

from unittest.mock import patch

from testing.integration.app_factory import bearer, client


def test_get_job_401_anonymous():
    res = client().get("/api/jobs/abc")
    assert res.status_code == 401


def test_get_job_404_when_missing():
    headers, _, _ = bearer()
    with patch("app.routers.jobs.job_store.get", return_value=None):
        res = client().get("/api/jobs/507f1f77bcf86cd799439011", headers=headers)
    assert res.status_code == 404
    assert res.json()["detail"] == "Job not found."


def test_get_job_403_when_owned_by_someone_else():
    headers, user_id, _ = bearer()
    with patch(
        "app.routers.jobs.job_store.get",
        return_value={"_id": "j1", "user_id": "someone-else", "kind": "chat",
                      "status": "queued", "progress": {}},
    ):
        res = client().get("/api/jobs/j1", headers=headers)
    assert res.status_code == 403


def test_get_job_200_serializes_status_and_progress():
    headers, user_id, _ = bearer()
    with patch(
        "app.routers.jobs.job_store.get",
        return_value={
            "_id": "j1",
            "user_id": user_id,
            "kind": "ingest",
            "status": "running",
            "progress": {"message": "Embedding page 2/4"},
            "result": None,
            "error": None,
            "params": {"document_id": "d1"},
        },
    ):
        res = client().get("/api/jobs/j1", headers=headers)
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "running"
    assert body["progress"]["message"] == "Embedding page 2/4"
    assert body["kind"] == "ingest"
