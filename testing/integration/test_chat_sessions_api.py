"""I-07 — chat session rename and listing (`app/routers/chat.py`), service mocked."""

from unittest.mock import patch

from testing.integration.app_factory import bearer, client


def test_rename_session_401_without_token():
    res = client().patch("/api/chat/sessions/s1", json={"title": "New name"})
    assert res.status_code == 401


def test_rename_session_422_on_blank_title_before_it_reaches_the_service():
    headers, _, _ = bearer()
    res = client().patch("/api/chat/sessions/s1", headers=headers, json={"title": ""})
    assert res.status_code == 422


def test_rename_session_200_returns_updated_session():
    headers, _, _ = bearer()
    with patch(
        "app.routers.chat.service.rename_session",
        return_value={"id": "s1", "title": "Directors' duties"},
    ):
        res = client().patch(
            "/api/chat/sessions/s1", headers=headers, json={"title": "Directors' duties"}
        )
    assert res.status_code == 200
    assert res.json()["title"] == "Directors' duties"


def test_rename_session_400_when_service_rejects_it():
    headers, _, _ = bearer()
    with patch(
        "app.routers.chat.service.rename_session",
        side_effect=ValueError("Give the conversation a name."),
    ):
        res = client().patch("/api/chat/sessions/s1", headers=headers, json={"title": "   "})
    assert res.status_code == 400
    assert "Give the conversation a name" in res.json()["detail"]


def test_list_sessions_401_without_token():
    res = client().get("/api/chat/sessions")
    assert res.status_code == 401


def test_list_sessions_200_with_token():
    headers, _, _ = bearer()
    with patch("app.routers.chat.service.list_sessions", return_value=[]):
        res = client().get("/api/chat/sessions", headers=headers)
    assert res.status_code == 200
    assert res.json() == []
