"""
The selectable-generator catalog.

`.env` (`LEARNMATE_GENERATOR_MODEL`) remains the fallback when a request omits `model_id`.
This file is what the UI lists, and what stops a failed-gate LoRA becoming the silent
default: `selectable_default` is only allowed on a model that is not `experimental`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional

from .. import config


def _coerce(value: str):
    lowered = value.lower()
    if lowered in ("true", "yes"):
        return True
    if lowered in ("false", "no"):
        return False
    if value.isdigit():
        return int(value)
    if value.startswith('"') and value.endswith('"'):
        return value[1:-1]
    return value


def _parse_registry(text: str) -> Dict:
    """Tiny YAML subset: `default_id` plus a list of scalar maps under `models:`."""
    default_id = None
    models: List[Dict] = []
    current: Optional[Dict] = None
    in_models = False

    for raw in text.splitlines():
        line = raw.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        stripped = line.strip()
        if stripped.startswith("default_id:"):
            default_id = _coerce(stripped.split(":", 1)[1].strip())
            continue
        if stripped == "models:" or stripped.startswith("models:"):
            in_models = True
            continue
        if not in_models:
            continue
        if stripped.startswith("- "):
            if current:
                models.append(current)
            current = {}
            rest = stripped[2:]
            if ":" in rest:
                key, val = rest.split(":", 1)
                current[key.strip()] = _coerce(val.strip())
            continue
        if current is not None and ":" in stripped:
            key, val = stripped.split(":", 1)
            current[key.strip()] = _coerce(val.strip())
    if current:
        models.append(current)
    return {"default_id": default_id, "models": models}


def _resolve_path(gguf_path: str) -> Path:
    path = Path(gguf_path)
    if path.is_absolute():
        return path
    under_models = config.MODELS_DIR / path
    if under_models.exists() or not (config.ROOT_DIR / path).exists():
        return under_models
    return config.ROOT_DIR / path


def load_catalog() -> Dict:
    path = config.MODELS_REGISTRY_PATH
    if not path.is_file():
        return {"default_id": "qwen25-3b", "models": []}
    parsed = _parse_registry(path.read_text(encoding="utf-8"))
    for entry in parsed["models"]:
        entry["resolved_path"] = str(_resolve_path(str(entry.get("gguf_path") or "")))
        entry["available"] = Path(entry["resolved_path"]).is_file()
        if entry.get("selectable_default") and entry.get("experimental"):
            # A failed-gate model must not become the silent default.
            entry["selectable_default"] = False
    return parsed


def get_entry(model_id: Optional[str]) -> Optional[Dict]:
    if not model_id:
        return None
    wanted = str(model_id).strip()
    for entry in load_catalog()["models"]:
        if entry.get("id") == wanted:
            return entry
    return None


def public_models() -> List[Dict]:
    """What GET /api/models returns — no filesystem paths."""
    catalog = load_catalog()
    rows = []
    for entry in catalog["models"]:
        rows.append({
            "id": entry.get("id"),
            "display_name": entry.get("display_name") or entry.get("id"),
            "context_length": entry.get("context_length"),
            "role_hint": entry.get("role_hint") or "",
            "experimental": bool(entry.get("experimental")),
            "selectable_default": bool(entry.get("selectable_default")),
            "available": bool(entry.get("available")),
            "is_catalog_default": entry.get("id") == catalog.get("default_id"),
        })
    return rows
