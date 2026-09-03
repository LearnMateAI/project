"""
Shared paths and a tiny YAML subset parser for comparison_registry.yaml.

The live catalog parser in learnmate.llm.catalog only understands `default_id` + `models`.
This file understands several named lists of scalar maps (generators, judges, …).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Dict, List, Optional

DOCS_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = DOCS_DIR.parent.parent
BACKEND_DIR = REPO_ROOT / "integrated-backend"
FIXTURES_DIR = DOCS_DIR / "fixtures"
RESULTS_DIR = DOCS_DIR / "results"
REGISTRY_PATH = DOCS_DIR / "comparison_registry.yaml"


def ensure_backend_on_path() -> None:
    """Import learnmate from integrated-backend (also sets HF_HOME via config)."""
    path = str(BACKEND_DIR)
    if path not in sys.path:
        sys.path.insert(0, path)


def _coerce(value: str):
    lowered = value.lower()
    if lowered in ("true", "yes"):
        return True
    if lowered in ("false", "no"):
        return False
    if value.isdigit():
        return int(value)
    if (value.startswith('"') and value.endswith('"')) or (
            value.startswith("'") and value.endswith("'")):
        return value[1:-1]
    return value


def parse_named_lists(text: str) -> Dict[str, List[Dict]]:
    """Parse `name:` blocks of `- key: value` maps. Comments and blanks are ignored."""
    lists: Dict[str, List[Dict]] = {}
    current_name: Optional[str] = None
    current: Optional[Dict] = None

    for raw in text.splitlines():
        line = raw.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        stripped = line.strip()
        # List headers live at column 0 (`embeddings:`). Indented `key: "value:"` lines
        # are map fields — they must not open a new list just because the value ends
        # with a colon (BGE's query prefix does).
        if (line[:1] not in " \t"
                and stripped.endswith(":")
                and not stripped.startswith("- ")
                and stripped.index(":") == len(stripped) - 1):
            key = stripped[:-1].strip()
            if current is not None and current_name:
                lists.setdefault(current_name, []).append(current)
                current = None
            current_name = key
            lists.setdefault(current_name, [])
            continue
        if current_name is None:
            continue
        if stripped.startswith("- "):
            if current is not None:
                lists[current_name].append(current)
            current = {}
            rest = stripped[2:]
            if ":" in rest:
                key, val = rest.split(":", 1)
                current[key.strip()] = _coerce(val.strip())
            continue
        if current is not None and ":" in stripped:
            key, val = stripped.split(":", 1)
            current[key.strip()] = _coerce(val.strip())
    if current is not None and current_name:
        lists[current_name].append(current)
    return lists


def load_comparison_registry() -> Dict[str, List[Dict]]:
    return parse_named_lists(REGISTRY_PATH.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> List[Dict]:
    rows = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            rows.append(json.loads(line))
    return rows


def write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def models_dir() -> Path:
    ensure_backend_on_path()
    from learnmate import config
    return Path(config.MODELS_DIR)
