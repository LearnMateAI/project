"""I-06 — GET /api/models (`app/routers/models.py`). Reads the real registry file,
no Mongo, no GGUF load."""

from testing.integration.app_factory import bearer, client


def test_models_401_without_token():
    res = client().get("/api/models")
    assert res.status_code == 401


def test_models_200_lists_catalog_without_filesystem_paths():
    headers, _, _ = bearer()
    res = client().get("/api/models", headers=headers)
    assert res.status_code == 200
    rows = res.json()
    assert isinstance(rows, list) and rows
    for row in rows:
        assert "gguf_path" not in row
        assert "resolved_path" not in row
        assert "id" in row and "display_name" in row
    assert sum(1 for row in rows if row["is_catalog_default"]) == 1
