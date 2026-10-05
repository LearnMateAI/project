"""
Unit tests for the confusion heatmap (learnmate/insights).

No Mongo and no embedding model: pipelines are checked for shape, clustering runs on
synthetic vectors, and the end-to-end computation gets its rows passed in.
"""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone
from unittest import mock

import numpy as np

from learnmate import config
from learnmate.insights import aggregate, cluster, confusion, service

WEIGHTS = confusion.parse_weights("general=1,low_score=1,rejected=1,repeat=1")


class CtfidfTests(unittest.TestCase):
    def test_distinctive_terms_win_and_question_words_are_dropped(self):
        labels = cluster.ctfidf({
            0: ["Explain the doctrine of estoppel", "What is promissory estoppel?"],
            1: ["What are directors' fiduciary duties?", "Explain duties of directors"],
        }, top_n=2)
        self.assertEqual(labels[0][0], "estoppel")
        self.assertIn("directors", labels[1])
        self.assertNotIn("explain", labels[0] + labels[1])

    def test_empty_cluster(self):
        self.assertEqual(cluster.ctfidf({0: ["what is it?"]}), {0: []})


class ClusterTests(unittest.TestCase):
    def test_separated_blobs_become_clusters(self):
        rng = np.random.default_rng(0)
        centres = np.eye(384)[:3] * 1.0
        points = np.vstack([c + rng.normal(0, 0.01, (12, 384)) for c in centres])
        points /= np.linalg.norm(points, axis=1, keepdims=True)
        labels = cluster.cluster(points, min_cluster_size=4, min_samples=2)
        self.assertEqual(len(set(labels) - {-1}), 3)

    def test_too_few_points_is_all_noise(self):
        self.assertEqual(list(cluster.cluster(np.ones((2, 4)), 3, 2)), [-1, -1])


def _stat(page, questions, users, general=0, judged=0, low=0, rejected=0):
    return {"page": page, "questions": questions, "distinct_users": users,
            "general": general, "judged": judged, "low": low, "rejected": rejected,
            "cache_hits": 0}


class PageConfusionTests(unittest.TestCase):
    def test_every_page_is_present_and_small_groups_are_suppressed(self):
        pages = confusion.page_confusion(
            [_stat(2, 10, 5, general=5), _stat(4, 3, 2)], {}, n_pages=5,
            weights=WEIGHTS, k=3)
        self.assertEqual([p["page"] for p in pages], [1, 2, 3, 4, 5])
        self.assertTrue(pages[3]["suppressed"])
        self.assertIsNone(pages[3]["questions"])
        self.assertEqual(pages[0]["questions"], 0)
        self.assertFalse(pages[0]["suppressed"])

    def test_formula(self):
        pages = confusion.page_confusion(
            [_stat(1, 10, 4, general=5, judged=4, low=2, rejected=1)], {1: 2}, n_pages=1,
            weights=WEIGHTS, k=3)
        signals = {"general": 0.5, "low_score": 0.5, "rejected": 0.25, "repeat": 0.2}
        expected = 1.0 * (1 + sum(signals.values())) / (1 + 4)
        self.assertAlmostEqual(pages[0]["confusion"], round(expected, 4))
        self.assertEqual(pages[0]["signals"], signals)

    def test_quiet_page_scores_below_troubled_page_of_equal_volume(self):
        pages = confusion.page_confusion(
            [_stat(1, 10, 4), _stat(2, 10, 4, general=10)], {}, 2, WEIGHTS, 3)
        self.assertLess(pages[0]["confusion"], pages[1]["confusion"])

    def test_weights_parse(self):
        self.assertEqual(confusion.parse_weights("general=2,bogus=5,repeat=x")["general"], 2.0)
        self.assertEqual(confusion.parse_weights("")["repeat"], 1.0)


class RepeatTests(unittest.TestCase):
    def test_same_student_same_topic_within_window(self):
        t0 = datetime(2026, 9, 1, tzinfo=timezone.utc)
        rows = [{"user_id": "a", "created_at": t0},
                {"user_id": "a", "created_at": t0 + timedelta(days=1)},
                {"user_id": "b", "created_at": t0 + timedelta(days=1)},
                {"user_id": "a", "created_at": t0 + timedelta(days=30)},
                {"user_id": "a", "created_at": t0 + timedelta(days=31)}]
        flags = confusion.repeat_flags(rows, [0, 0, 0, 0, -1], days=7)
        self.assertEqual(flags, [False, True, False, False, False])


class TopicSummaryTests(unittest.TestCase):
    def test_topics_below_k_students_are_dropped(self):
        rows = [{"user_id": u, "mode": "pdf", "score": 80, "accepted": True, "page": 3}
                for u in ("a", "b", "c", "a", "a")]
        summary = confusion.topic_summary(rows, [0, 0, 0, 1, 1], {0: ["trust"], 1: ["lien"]},
                                          [False] * 5, WEIGHTS, k=3, low_score=70)
        self.assertEqual([t["id"] for t in summary["topics"]], [0])
        self.assertEqual(summary["suppressed_topics"], 1)
        self.assertEqual(summary["topics"][0]["pages"], [{"page": 3, "share": 1.0}])
        self.assertNotIn("question", summary["topics"][0])


class PipelineShapeTests(unittest.TestCase):
    def test_rows_pair_questions_through_a_window_function(self):
        stages = aggregate.question_rows_pipeline("oid")
        names = [next(iter(stage)) for stage in stages]
        self.assertEqual(names[:3], ["$match", "$setWindowFields", "$match"])
        window = stages[1]["$setWindowFields"]
        self.assertEqual(window["partitionBy"], "$session_id")
        self.assertIn("$shift", window["output"]["prev_content"])

    def test_page_stats_is_one_facet_query(self):
        stages = aggregate.page_stats_pipeline("oid", 70)
        facet = stages[-1]["$facet"]
        self.assertEqual(set(facet), {"pages", "totals"})
        group = facet["pages"][1]["$group"]
        self.assertEqual(group["users"], {"$addToSet": "$user_id"})


class ComputeTests(unittest.TestCase):
    def test_end_to_end_without_mongo_or_models(self):
        t0 = datetime(2026, 9, 1, tzinfo=timezone.utc)
        rows, vectors = [], []
        rng = np.random.default_rng(1)
        for topic, (page, words) in enumerate([(2, "estoppel promise reliance"),
                                               (5, "director fiduciary loyalty")]):
            for i in range(8):
                rows.append({"user_id": f"u{i % 4}", "question": f"What is {words}?",
                             "mode": "general" if topic == 0 else "pdf",
                             "score": None if topic == 0 else 85, "accepted": True,
                             "page": page, "created_at": t0 + timedelta(hours=i)})
                v = np.zeros(384)
                v[topic] = 1.0
                vectors.append(v + rng.normal(0, 0.01, 384))
        vectors = np.array(vectors)
        vectors /= np.linalg.norm(vectors, axis=1, keepdims=True)
        stats = {"pages": [_stat(2, 8, 4, general=8), _stat(5, 8, 4, judged=8)],
                 "totals": {"questions": 16, "distinct_users": 4, "unattributed": 0}}
        with mock.patch.object(cluster, "embed", return_value=vectors), \
                mock.patch.object(config, "INSIGHTS_MIN_QUESTIONS", 5):
            result = service.compute_heatmap("doc", rows=rows, stats=stats, n_pages=6)
        self.assertEqual(len(result["pages"]), 6)
        self.assertGreater(result["pages"][1]["confusion"], result["pages"][4]["confusion"])
        self.assertEqual(len(result["topics"]), 2)
        self.assertEqual(result["topics"][0]["pages"][0]["page"], 2)
        public = service._public(result)
        self.assertNotIn("_labels", public)
        self.assertNotIn("question", str(public["topics"]))


if __name__ == "__main__":
    unittest.main()
