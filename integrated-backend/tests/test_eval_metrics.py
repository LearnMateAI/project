"""
Hand-checked tests for the evaluation metrics (eval/metrics.py) and the workload helpers.

Every number in the paper passes through these functions, so each is checked against a
value worked out by hand.
"""

from __future__ import annotations

import math
import unittest

from eval import metrics


class RankingMetricTests(unittest.TestCase):
    RANKED = ["a", "b", "g", "c"]

    def test_recall(self):
        self.assertEqual(metrics.recall_at_k(self.RANKED, ["g"], 2), 0.0)
        self.assertEqual(metrics.recall_at_k(self.RANKED, ["g"], 3), 1.0)

    def test_mrr(self):
        self.assertAlmostEqual(metrics.mrr_at_k(self.RANKED, ["g"], 10), 1 / 3)
        self.assertEqual(metrics.mrr_at_k(self.RANKED, ["z"], 10), 0.0)

    def test_graded_ndcg(self):
        # gold g=2 at rank 3, same-page b=1 at rank 2.
        grades = {"g": 2, "b": 1}
        dcg = (2 ** 1 - 1) / math.log2(3) + (2 ** 2 - 1) / math.log2(4)
        ideal = (2 ** 2 - 1) / math.log2(2) + (2 ** 1 - 1) / math.log2(3)
        self.assertAlmostEqual(metrics.ndcg_at_k(self.RANKED, grades, 10), dcg / ideal)
        self.assertAlmostEqual(metrics.ndcg_at_k(["g", "b"], grades, 10), 1.0)


class SummaryTests(unittest.TestCase):
    def test_percentile_interpolates(self):
        self.assertEqual(metrics.percentile([1, 2, 3, 4], 50), 2.5)
        self.assertEqual(metrics.percentile([5], 95), 5)
        self.assertIsNone(metrics.percentile([], 50))

    def test_prf1(self):
        scores = metrics.prf1(tp=8, fp=2, fn=8)
        self.assertAlmostEqual(scores["precision"], 0.8)
        self.assertAlmostEqual(scores["recall"], 0.5)
        self.assertAlmostEqual(scores["f1"], 2 * 0.8 * 0.5 / 1.3)

    def test_bootstrap_is_deterministic_and_directional(self):
        a, b = [0.0] * 30, [1.0] * 30
        self.assertEqual(metrics.paired_bootstrap(a, b), metrics.paired_bootstrap(a, b))
        self.assertEqual(metrics.paired_bootstrap(a, b)["p_value"], 0.0)
        self.assertEqual(metrics.paired_bootstrap(b, a)["p_value"], 1.0)

    def test_nmi_ari_perfect_and_noise_handling(self):
        perfect = metrics.nmi_ari(["x", "x", "y", "y"], [0, 0, 1, 1])
        self.assertAlmostEqual(perfect["nmi"], 1.0)
        self.assertAlmostEqual(perfect["ari"], 1.0)
        dropped = metrics.nmi_ari(["x", "x", "y", "y"], [0, 0, -1, -1])
        self.assertEqual(dropped["n"], 2)


class WorkloadCleanupTests(unittest.TestCase):
    def test_prompt_echo_is_removed(self):
        from eval.workload import _clean

        self.assertEqual(_clean("What is a tort according to the course notes?"),
                         "What is a tort?")
        self.assertEqual(_clean("What notes must a promissory note contain"),
                         "What notes must a promissory note contain?")


if __name__ == "__main__":
    unittest.main()
