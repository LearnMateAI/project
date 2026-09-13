"""I-04 — chat and resources reject anonymous callers and accept a token shape."""

from unittest.mock import patch

from testing.integration.app_factory import bearer, client


def test_create_chat_session_401():
    res = client().post(
        "/api/chat/sessions",
        json={"document_id": "507f1f77bcf86cd799439011"},
    )
    assert res.status_code == 401


def test_generate_resource_401():
    res = client().post(
        "/api/resources/generate",
        json={"document_id": "507f1f77bcf86cd799439011", "resource_type": "mcq"},
    )
    assert res.status_code == 401


def test_send_message_202_when_ownership_and_queue_ok():
    headers, _, _ = bearer()
    with patch("app.routers.chat.access.require_session"), patch(
        "app.routers.chat.enqueue",
        return_value={"_id": "job-chat", "status": "queued"},
    ):
        res = client().post(
            "/api/chat/sessions/s1/messages",
            headers=headers,
            json={"message": "What is section 108?"},
        )
    assert res.status_code == 202
    body = res.json()
    assert body["job_id"] == "job-chat"
    assert body["kind"] == "chat"
    assert body["status"] == "queued"
