"""
F-01: client evaluate=false must not skip the judge unless an env flag allows it.
"""

from __future__ import annotations

import unittest
from unittest.mock import patch

from app.services.evaluate_policy import resolve_evaluate


class ResolveEvaluateTests(unittest.TestCase):
    def test_production_ignores_client_false(self):
        with patch("app.services.evaluate_policy.engine_config.ALLOW_CLIENT_EVALUATE", False):
            self.assertTrue(resolve_evaluate(False))
            self.assertTrue(resolve_evaluate(True))
            self.assertTrue(resolve_evaluate(None))

    def test_lab_flag_honours_client(self):
        with patch("app.services.evaluate_policy.engine_config.ALLOW_CLIENT_EVALUATE", True):
            self.assertFalse(resolve_evaluate(False))
            self.assertTrue(resolve_evaluate(True))
            self.assertTrue(resolve_evaluate(None))


if __name__ == "__main__":
    unittest.main()
