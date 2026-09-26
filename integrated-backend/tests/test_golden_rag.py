"""Smoke-test the offline golden eval: current profile must beat baseline on F-03."""

from __future__ import annotations

import unittest

from eval.golden_rag import run


class GoldenCompareTests(unittest.TestCase):
    def test_current_abstains_where_baseline_invents(self):
        before = run("baseline")["summary"]
        after = run("current")["summary"]
        self.assertEqual(before["oos_abstain_rate"], 0.0)
        self.assertEqual(after["oos_abstain_rate"], 1.0)
        self.assertGreater(before["oos_invented_rate"], 0.0)
        self.assertEqual(after["oos_invented_rate"], 0.0)
        self.assertFalse(before["injection_contained"])
        self.assertTrue(after["injection_contained"])
        self.assertFalse(before["evaluate_false_ignored"])
        self.assertTrue(after["evaluate_false_ignored"])
        self.assertGreater(after["faithfulness"], before["faithfulness"])


if __name__ == "__main__":
    unittest.main()
