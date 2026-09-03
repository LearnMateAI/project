"""Registry contract for thevindu-models comparison entries.

No GGUF download: we only check that Qwen stays the silent default and that the
comparison generators cannot become selectable_default while experimental.
"""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

from learnmate.llm import catalog

REPO_ROOT = Path(__file__).resolve().parents[2]


class ModelsRegistryTests(unittest.TestCase):
    def test_qwen_remains_silent_default(self):
        loaded = catalog.load_catalog()
        self.assertEqual(loaded["default_id"], "qwen25-3b")
        by_id = {row["id"]: row for row in loaded["models"]}
        self.assertIn("qwen25-3b", by_id)
        self.assertFalse(by_id["qwen25-3b"].get("experimental"))
        self.assertTrue(by_id["qwen25-3b"].get("selectable_default"))

    def test_comparison_generators_are_experimental(self):
        by_id = {row["id"]: row for row in catalog.load_catalog()["models"]}
        for model_id in ("gemma2-2b", "phi35-mini", "legal-1.5b"):
            self.assertIn(model_id, by_id, model_id)
            self.assertTrue(by_id[model_id].get("experimental"), model_id)
            self.assertFalse(by_id[model_id].get("selectable_default"), model_id)

    def test_comparison_yaml_keeps_colon_in_bge_prefix(self):
        path = REPO_ROOT / "docs" / "thevindu-models" / "scripts" / "common.py"
        spec = importlib.util.spec_from_file_location("thevindu_models_common", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        registry = module.load_comparison_registry()
        bge = next(row for row in registry["embeddings"] if row["id"] == "bge-small")
        self.assertIn("searching relevant passages:", bge["query_prefix"])
        e5 = next(row for row in registry["embeddings"] if row["id"] == "e5-small")
        self.assertEqual(e5["query_prefix"], "query:")
        self.assertEqual(e5["doc_prefix"], "passage:")
        self.assertEqual(len(registry["generators"]), 3)
        self.assertEqual(len(registry["judges"]), 3)
        self.assertEqual(len(registry["rerankers"]), 3)
        self.assertEqual(len(registry["agents"]), 2)


if __name__ == "__main__":
    unittest.main()
