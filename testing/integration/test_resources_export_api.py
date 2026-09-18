"""I-08 — GET /api/resources/{id}/export (`app/routers/resources.py`), export service mocked."""

from unittest.mock import patch

from testing.integration.app_factory import bearer, client


def test_export_401_without_token():
    res = client().get("/api/resources/r1/export")
    assert res.status_code == 401


def test_export_422_on_unsupported_format_query_value():
    headers, _, _ = bearer()
    res = client().get("/api/resources/r1/export?format=xlsx", headers=headers)
    assert res.status_code == 422


def test_export_200_streams_docx_with_content_disposition():
    headers, _, _ = bearer()
    fake = (
        b"PK\x03\x04fake-docx-bytes",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "act_summary.docx",
    )
    with patch("app.routers.resources.export_service.export_resource", return_value=fake):
        res = client().get("/api/resources/r1/export", headers=headers)
    assert res.status_code == 200
    assert res.content == fake[0]
    assert res.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    assert 'filename="act_summary.docx"' in res.headers["content-disposition"]


def test_export_404_when_resource_not_owned():
    from app.errors import NotFound

    headers, _, _ = bearer()
    with patch(
        "app.routers.resources.export_service.export_resource",
        side_effect=NotFound("Resource not found."),
    ):
        res = client().get("/api/resources/r1/export?format=pptx", headers=headers)
    assert res.status_code == 404
    assert res.json()["detail"] == "Resource not found."


def test_export_400_when_format_argument_is_rejected_by_the_service():
    headers, _, _ = bearer()
    with patch(
        "app.routers.resources.export_service.export_resource",
        side_effect=ValueError("Export format must be docx or pptx."),
    ):
        res = client().get("/api/resources/r1/export?format=pptx", headers=headers)
    assert res.status_code == 400
