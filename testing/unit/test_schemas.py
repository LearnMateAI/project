"""U-03 — request bodies the React client actually posts (`app/schemas.py`)."""

import pytest
from pydantic import ValidationError

from app.schemas import (
    RESOURCE_TYPES,
    CreateSessionRequest,
    GenerateRequest,
    LoginRequest,
    RegisterRequest,
    SendMessageRequest,
)


def test_register_requires_real_email_and_name():
    with pytest.raises(ValidationError):
        RegisterRequest(name="", email="not-an-email", password="x")
    ok = RegisterRequest(name="Ada", email="ada@uni.lk", password="Password1")
    assert ok.email == "ada@uni.lk"


def test_login_rejects_invalid_email():
    with pytest.raises(ValidationError):
        LoginRequest(email="nope", password="Password1")


def test_generate_scope_must_be_passage_or_document():
    with pytest.raises(ValidationError):
        GenerateRequest(document_id="abc", resource_type="mcq", scope="chapter")
    body = GenerateRequest(document_id="abc", resource_type="keypoints")
    assert body.scope == "passage"
    assert body.evaluate is True


def test_generate_count_bounds():
    with pytest.raises(ValidationError):
        GenerateRequest(document_id="abc", resource_type="mcq", count=0)
    with pytest.raises(ValidationError):
        GenerateRequest(document_id="abc", resource_type="mcq", count=201)


def test_frontend_aliases_are_accepted_resource_types():
    assert "key_points" in RESOURCE_TYPES
    assert "explanation_summary" in RESOURCE_TYPES
    assert "mcq" in RESOURCE_TYPES


def test_chat_message_length_bounds():
    with pytest.raises(ValidationError):
        SendMessageRequest(message="")
    with pytest.raises(ValidationError):
        SendMessageRequest(message="x" * 4001)
    ok = SendMessageRequest(message="What is section 108?")
    assert ok.evaluate is True


def test_create_session_requires_document_id():
    with pytest.raises(ValidationError):
        CreateSessionRequest()
    CreateSessionRequest(document_id="507f1f77bcf86cd799439011")


def test_summary_style_accepts_narrative_structured_auto_or_omitted():
    assert GenerateRequest(document_id="abc", resource_type="summary").summary_style is None
    for style in ("narrative", "structured", "auto"):
        body = GenerateRequest(document_id="abc", resource_type="summary", summary_style=style)
        assert body.summary_style == style
    with pytest.raises(ValidationError):
        GenerateRequest(document_id="abc", resource_type="summary", summary_style="bulleted")


def test_difficulty_accepts_easy_medium_hard_or_omitted():
    assert GenerateRequest(document_id="abc", resource_type="mcq").difficulty is None
    for level in ("easy", "medium", "hard"):
        body = GenerateRequest(document_id="abc", resource_type="mcq", difficulty=level)
        assert body.difficulty == level
    with pytest.raises(ValidationError):
        GenerateRequest(document_id="abc", resource_type="mcq", difficulty="impossible")


def test_rename_session_schema_rejects_empty_but_not_whitespace_title():
    from app.schemas import RenameSessionRequest

    with pytest.raises(ValidationError):
        RenameSessionRequest(title="")
    # The schema only enforces min_length=1; a whitespace-only title passes here and is
    # rejected downstream by app.services.chat.rename_session (see test_chat_service.py).
    assert RenameSessionRequest(title="   ").title == "   "
    assert RenameSessionRequest(title="Contract law revision").title == "Contract law revision"
