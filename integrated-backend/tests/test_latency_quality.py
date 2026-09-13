"""
Unit tests for the latency / quality / failure work on thevindu-feature.

No Mongo, Qdrant, or GGUF: these check the new seams in isolation so they can run
without the live stack. The running-server check is separate (health + frontend).
"""

from __future__ import annotations

import json
import time
import unittest

from learnmate.chat_agent import persist as chat_persist
from learnmate.chat_agent.rewrite import _needs_rewrite
from learnmate.resource_agent import persist as resource_persist
from learnmate.retrieval.bm25 import BM25Okapi, tokenize
from learnmate.runtime_limits import (
    JobTimeout,
    add_timing,
    check_job_deadline,
    clear_deadline,
    set_deadline_seconds,
)
from learnmate.storage import bm25_store

from app.jobs.worker import _error_code
from learnmate.storage.mongo import StorageUnavailable
from learnmate.storage.qdrant_vectors import QdrantUnavailable


class TimingTests(unittest.TestCase):
    def test_add_timing_accumulates(self):
        started = time.perf_counter()
        time.sleep(0.02)
        first = add_timing({}, "generate_ms", started)
        self.assertGreaterEqual(first["generate_ms"], 15)
        second = add_timing({"timings": first}, "generate_ms", started)
        self.assertGreater(second["generate_ms"], first["generate_ms"])
        self.assertNotIn("judge_ms", second)

    def test_add_timing_does_not_mutate_input(self):
        state = {"timings": {"rewrite_ms": 4}}
        out = add_timing(state, "retrieve_ms", time.perf_counter())
        self.assertEqual(state["timings"], {"rewrite_ms": 4})
        self.assertEqual(out["rewrite_ms"], 4)
        self.assertIn("retrieve_ms", out)


class DeadlineTests(unittest.TestCase):
    def tearDown(self):
        clear_deadline()

    def test_zero_disables_deadline(self):
        set_deadline_seconds(0)
        check_job_deadline()

    def test_expired_deadline_raises_job_timeout(self):
        set_deadline_seconds(1)
        # Force the stored deadline into the past.
        from learnmate import runtime_limits

        runtime_limits._deadline.set(time.monotonic() - 1)
        with self.assertRaises(JobTimeout):
            check_job_deadline()


class ResourceBestAttemptTests(unittest.TestCase):
    def test_keeps_higher_score_not_the_later_retry(self):
        state = {
            "threshold": 70,
            "verbose": False,
            "attempts": [
                {"attempt": 1, "score": 80, "passed": True, "content": "first",
                 "verdict": {"score": 80}},
                {"attempt": 2, "score": 50, "passed": False, "content": "second",
                 "verdict": {"score": 50}},
            ],
            "passed": False,
            "content": "second",
        }
        content, verdict, passed = resource_persist.best_attempt(state)
        self.assertEqual(content, "first")
        self.assertTrue(passed)
        self.assertEqual(verdict["score"], 80)

    def test_unscored_attempts_keep_last(self):
        state = {
            "threshold": 70,
            "verbose": False,
            "passed": False,
            "attempts": [
                {"attempt": 1, "score": None, "content": "a", "verdict": None},
                {"attempt": 2, "score": None, "content": "b", "verdict": None},
            ],
        }
        content, _, passed = resource_persist.best_attempt(state)
        self.assertEqual(content, "b")
        self.assertFalse(passed)

    def test_persist_false_returns_winner_without_mongo(self):
        state = {
            "task": "summary",
            "threshold": 70,
            "persist": False,
            "verbose": False,
            "evaluate": True,
            "count": 3,
            "attempts": [
                {"attempt": 1, "score": 90, "passed": True, "content": "keep",
                 "verdict": {"score": 90}},
                {"attempt": 2, "score": 40, "passed": False, "content": "drop",
                 "verdict": {"score": 40}},
            ],
        }
        result = resource_persist.persist_node(state)
        self.assertEqual(result["content"], "keep")
        self.assertTrue(result["passed"])
        self.assertIsNone(result["resource_id"])


class ChatBestAttemptTests(unittest.TestCase):
    def test_keeps_best_reply(self):
        state = {
            "threshold": 70,
            "verbose": False,
            "attempts": [
                {"attempt": 1, "reply": "grounded", "verdict": {"score": 88}},
                {"attempt": 2, "reply": "worse", "verdict": {"score": 40}},
            ],
        }
        reply, verdict, passed = chat_persist.best_attempt(state)
        self.assertEqual(reply, "grounded")
        self.assertTrue(passed)
        self.assertEqual(verdict["score"], 88)


class Bm25Tests(unittest.TestCase):
    def tearDown(self):
        bm25_store._OKAPI_CACHE.clear()

    def test_word_tokens_rank_the_matching_chunk(self):
        docs = [
            tokenize("the directors owe fiduciary duties to the company"),
            tokenize("a recipe for coconut sambol and rice"),
        ]
        index = BM25Okapi(docs)
        ranked = index.ranked("fiduciary duties of directors", top_k=2)
        self.assertTrue(ranked)
        self.assertEqual(ranked[0][0], 0)

    def test_character_corpus_does_not_match_word_query(self):
        # The pre-cache bug: passing raw strings made each character a term.
        index = BM25Okapi(["fiduciary duties of directors"])
        ranked = index.ranked("fiduciary duties", top_k=5)
        self.assertEqual(ranked, [])

    def test_invalidate_drops_cached_index(self):
        bm25_store._OKAPI_CACHE["abc"] = ("index", [])
        bm25_store.invalidate_cache("abc")
        self.assertNotIn("abc", bm25_store._OKAPI_CACHE)


class ErrorCodeTests(unittest.TestCase):
    def test_timeout(self):
        self.assertEqual(_error_code(JobTimeout("late")), "timeout")

    def test_storage(self):
        self.assertEqual(_error_code(StorageUnavailable("mongo down")), "storage")
        self.assertEqual(_error_code(QdrantUnavailable("qdrant down")), "storage")

    def test_model(self):
        self.assertEqual(_error_code(ValueError("unknown model_id 'x'")), "model")
        self.assertEqual(_error_code(RuntimeError("could not load GGUF")), "model")

    def test_parse(self):
        self.assertEqual(_error_code(json.JSONDecodeError("msg", "doc", 0)), "parse")

    def test_unknown(self):
        self.assertEqual(_error_code(RuntimeError("something else")), "unknown")


class RewriteHeuristicTests(unittest.TestCase):
    def test_standalone_first_turn_skips_llm(self):
        self.assertFalse(_needs_rewrite("What are the directors' duties?", []))

    def test_follow_up_needs_rewrite(self):
        history = [{"role": "assistant", "content": "Directors owe fiduciary duties."}]
        self.assertTrue(_needs_rewrite("what about his powers?", history))


if __name__ == "__main__":
    unittest.main()
