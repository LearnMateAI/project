"""U-17 — selectable generator catalog (`learnmate/llm/catalog.py`).

No GGUF is loaded; `load_catalog` only parses `models_registry.yaml` and stats paths on
disk. The safety property under test: a failed-gate (`experimental: true`) entry can
never surface as `selectable_default`, even if the registry file says so.
"""

from __future__ import annotations

from pathlib import Path

from learnmate.llm.catalog import _parse_registry, get_entry, load_catalog, public_models


def test_parse_registry_reads_default_and_models():
    text = """
    default_id: qwen25-3b
    models:
      - id: qwen25-3b
        display_name: Qwen 2.5 3B Instruct
        context_length: 4096
        selectable_default: true
        experimental: false
      - id: legal-1.5b
        display_name: Sri Lankan legal domain 1.5B
        context_length: 4096
        selectable_default: false
        experimental: true
    """
    parsed = _parse_registry(text)
    assert parsed["default_id"] == "qwen25-3b"
    ids = [m["id"] for m in parsed["models"]]
    assert ids == ["qwen25-3b", "legal-1.5b"]
    assert parsed["models"][1]["experimental"] is True


def test_the_real_registry_file_loads_and_has_a_default():
    catalog = load_catalog()
    assert catalog["default_id"]
    ids = [m["id"] for m in catalog["models"]]
    assert catalog["default_id"] in ids


def test_experimental_entry_can_never_be_the_silent_default(tmp_path: Path, monkeypatch):
    """A failed-gate LoRA cannot become selectable_default even if the YAML says so.

    Exercises the real load_catalog() normalisation (not a re-implementation of it) by
    pointing it at a throwaway registry file with a rogue entry.
    """
    rogue_registry = tmp_path / "models_registry.yaml"
    rogue_registry.write_text(
        "default_id: failed-lora\n"
        "models:\n"
        "  - id: failed-lora\n"
        "    display_name: Failed gate candidate\n"
        "    gguf_path: does-not-exist.gguf\n"
        "    selectable_default: true\n"
        "    experimental: true\n",
        encoding="utf-8",
    )
    import learnmate.llm.catalog as catalog_module

    monkeypatch.setattr(catalog_module.config, "MODELS_REGISTRY_PATH", rogue_registry)
    catalog = load_catalog()
    entry = catalog["models"][0]
    assert entry["experimental"] is True
    assert entry["selectable_default"] is False


def test_get_entry_returns_none_for_missing_or_blank_id():
    assert get_entry(None) is None
    assert get_entry("") is None
    assert get_entry("does-not-exist") is None


def test_public_models_never_leaks_filesystem_paths():
    rows = public_models()
    assert rows, "expected at least one entry in the real registry"
    for row in rows:
        assert "gguf_path" not in row
        assert "resolved_path" not in row
        assert set(row) == {
            "id", "display_name", "context_length", "role_hint",
            "experimental", "selectable_default", "available", "is_catalog_default",
        }


def test_public_models_marks_exactly_one_catalog_default():
    rows = public_models()
    defaults = [row for row in rows if row["is_catalog_default"]]
    assert len(defaults) == 1


def test_no_public_model_is_both_experimental_and_selectable_default():
    for row in public_models():
        assert not (row["experimental"] and row["selectable_default"])
