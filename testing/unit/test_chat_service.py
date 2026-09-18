"""U-16 — chat session rename (`app/services/chat.py`), storage mocked.

`RenameSessionRequest` only enforces `min_length=1` (see test_schemas.py), so a
whitespace-only title must be caught here, before it reaches Mongo.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from app.services import chat as service


def test_rename_session_rejects_whitespace_only_title():
    with patch("app.services.chat.access.require_session", return_value={"_id": "s1"}):
        with pytest.raises(ValueError, match="Give the conversation a name"):
            service.rename_session("u1", "s1", "   ")


def test_rename_session_strips_and_truncates_title():
    with patch("app.services.chat.access.require_session", return_value={"_id": "s1"}), \
         patch("app.services.chat.content_store.rename_session", return_value=True) as renamed, \
         patch("app.services.chat.get_session", return_value={"id": "s1", "title": "x"}):
        service.rename_session("u1", "s1", "  Directors' duties  ")
    renamed.assert_called_once_with("s1", "Directors' duties")


def test_rename_session_raises_when_storage_reports_no_match():
    with patch("app.services.chat.access.require_session", return_value={"_id": "s1"}), \
         patch("app.services.chat.content_store.rename_session", return_value=False):
        with pytest.raises(ValueError, match="Could not rename"):
            service.rename_session("u1", "s1", "New title")
