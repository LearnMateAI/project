"""
Unit tests for the verified semantic answer cache (learnmate/cache, chat_agent/cache_nodes).

No Qdrant or models: the hit rule and the store policy are pure functions, the payload is
built without a server, and the nodes run against a mocked cache.
"""

from __future__ import annotations

import unittest
from datetime import datetime, timezone
from unittest import mock

from langchain_core.documents import Document

from learnmate import config
from learnmate.cache import answer_cache
from learnmate.cache.answer_cache import (
    PAYLOAD_FIELDS,
    AnswerCache,
    LookupResult,
    decide,
    normalize_query,
    should_store,
)
from learnmate.chat_agent import cache_nodes
from learnmate.chat_agent.graph import build_chat_graph


class DecideTests(unittest.TestCase):
    def test_empty_is_a_miss(self):
        self.assertEqual(decide([], [], 0.9, 0.5, True), (False, None, "miss_empty"))

    def test_below_tau_is_a_miss(self):
        self.assertEqual(decide([0.89], [None], 0.9, 0.5, True)[2], "miss_tau")

    def test_tau_is_inclusive(self):
        self.assertEqual(decide([0.9], [0.8], 0.9, 0.5, True), (True, 0, "hit"))

    def test_verifier_vetoes_a_near_duplicate(self):
        # "advantages of X" vs "disadvantages of X": very close embeddings, different asks.
        self.assertEqual(decide([0.96], [0.03], 0.9, 0.5, True)[2], "miss_verifier")

    def test_verifier_can_pick_a_lower_ranked_candidate(self):
        self.assertEqual(decide([0.97, 0.93], [0.1, 0.9], 0.9, 0.5, True), (True, 1, "hit"))

    def test_unavailable_verifier_is_a_miss_not_a_pass(self):
        self.assertEqual(decide([0.99], None, 0.9, 0.5, True)[2],
                         "miss_verifier_unavailable")

    def test_without_verifier_threshold_alone_decides(self):
        self.assertEqual(decide([0.95, 0.91], None, 0.9, 0.5, False), (True, 0, "hit"))


def _finished_turn(**overrides):
    state = {
        "query": "What is a fiduciary duty?",
        "standalone_query": "What is a fiduciary duty?",
        "mode": "pdf",
        "contexts": [Document(page_content="text", metadata={"page_number": 3})],
        "verdict": {"score": 88, "passed": True},
        "passed": True,
        "reply": "A duty of loyalty (p. 3).",
        "cache": {"hit": False},
    }
    state.update(overrides)
    return state


class StorePolicyTests(unittest.TestCase):
    def test_judged_grounded_accepted_answer_is_stored(self):
        self.assertEqual(should_store(_finished_turn()), (True, "stored"))

    def test_general_mode_is_never_stored(self):
        self.assertFalse(should_store(_finished_turn(mode="general", contexts=[]))[0])

    def test_gated_or_unjudged_is_never_stored(self):
        gated = {"score": None, "passed": True, "gated": True}
        self.assertEqual(should_store(_finished_turn(verdict=gated))[1], "skip:unjudged")
        self.assertEqual(should_store(_finished_turn(verdict=None))[1], "skip:unjudged")

    def test_low_score_or_rejected_is_not_stored(self):
        low = {"score": config.CACHE_MIN_SCORE - 1, "passed": False}
        self.assertEqual(should_store(_finished_turn(verdict=low))[1], "skip:low_score")
        self.assertEqual(should_store(_finished_turn(passed=False))[1], "skip:rejected")

    def test_rewritten_follow_up_is_not_stored(self):
        turn = _finished_turn(query="what about his powers?",
                              standalone_query="What are the President's powers?")
        self.assertEqual(should_store(turn)[1], "skip:followup")

    def test_a_hit_is_not_stored_again(self):
        self.assertEqual(should_store(_finished_turn(cache={"hit": True}))[1], "skip:hit")

    def test_empty_reply_is_not_stored(self):
        self.assertEqual(should_store(_finished_turn(reply="  "))[1], "skip:empty")


class PayloadTests(unittest.TestCase):
    def test_payload_carries_no_user_or_session_fields(self):
        cache = AnswerCache(embeddings=mock.Mock())
        info = {"doc_sha": "abc", "index_version": "2026-09-21T00:00:00"}
        contexts = [Document(page_content="chunk", metadata={"page_number": 4,
                                                             "chunk_index": 1})]
        payload = cache._payload("doc1", info, "Q?", "A.", contexts, [0.9], 90, 0.9, None)
        self.assertLessEqual(set(payload), PAYLOAD_FIELDS)
        for forbidden in ("user_id", "session_id", "user", "email"):
            self.assertNotIn(forbidden, payload)
        self.assertEqual(payload["citations"], [{"page": 4, "paragraph": 2}])
        self.assertGreater(payload["expires_at"], payload["created_at"])

    def test_normalisation_folds_case_space_and_trailing_punctuation(self):
        self.assertEqual(normalize_query("  What IS   a trust?? "), "what is a trust")

    def test_model_key_moves_with_prompt_version(self):
        first = answer_cache.model_key()
        with mock.patch.object(config, "CACHE_PROMPT_VERSION", "999"):
            self.assertNotEqual(first, answer_cache.model_key())
        self.assertNotEqual(answer_cache.model_key("qwen25-3b"),
                            answer_cache.model_key("legal-1.5b"))


class NodeTests(unittest.TestCase):
    def _state(self, **extra):
        state = {"query": "What is estoppel?", "standalone_query": "What is estoppel?",
                 "doc_id": "d1", "verbose": False, "threshold": 70, "use_cache": None}
        state.update(extra)
        return state

    def test_lookup_is_inert_when_disabled(self):
        with mock.patch.object(config, "CACHE_ENABLED", False):
            out = cache_nodes.cache_lookup_node(self._state())
        self.assertEqual(out["cache"]["hit"], False)
        self.assertEqual(cache_nodes.route_after_cache({**self._state(), **out}), "retrieve")

    def test_request_can_opt_out(self):
        with mock.patch.object(config, "CACHE_ENABLED", True):
            self.assertFalse(cache_nodes.cache_active(self._state(use_cache=False)))
            self.assertTrue(cache_nodes.cache_active(self._state()))

    def test_hit_short_circuits_with_the_cached_answer(self):
        fake = mock.Mock()
        fake.embeddings.embed_query.return_value = [0.1, 0.2]
        fake.lookup.return_value = LookupResult(
            hit=True, outcome="hit", similarity=0.95, verifier=0.9, entry_id="e1",
            payload={"answer": "Estoppel stops a party ... (p. 7).", "judge_score": 91,
                     "top_score": 0.97, "created_at": datetime.now(timezone.utc).timestamp(),
                     "contexts": [{"page_number": 7, "chunk_index": 0, "text": "chunk",
                                   "score": 0.97}]})
        with mock.patch.object(config, "CACHE_ENABLED", True), \
                mock.patch.object(cache_nodes, "get_answer_cache", return_value=fake):
            out = cache_nodes.cache_lookup_node(self._state())
        self.assertTrue(out["cache"]["hit"])
        self.assertEqual(out["mode"], "pdf")
        self.assertTrue(out["verdict"]["cached"])
        self.assertEqual(out["contexts"][0].metadata["page_number"], 7)
        self.assertEqual(out["query_vec"], [0.1, 0.2])
        self.assertEqual(cache_nodes.route_after_cache({**self._state(), **out}), "persist")

    def test_lookup_failure_degrades_to_no_cache(self):
        broken = mock.Mock()
        broken.embeddings.embed_query.side_effect = RuntimeError("qdrant down")
        with mock.patch.object(config, "CACHE_ENABLED", True), \
                mock.patch.object(cache_nodes, "get_answer_cache", return_value=broken):
            out = cache_nodes.cache_lookup_node(self._state())
        self.assertEqual(out["cache"], {"hit": False, "reason": "error"})

    def test_store_never_raises(self):
        broken = mock.Mock()
        broken.store.side_effect = RuntimeError("qdrant down")
        with mock.patch.object(config, "CACHE_ENABLED", True), \
                mock.patch.object(cache_nodes, "get_answer_cache", return_value=broken):
            self.assertEqual(cache_nodes.cache_store_node(
                {**_finished_turn(), "doc_id": "d1", "verbose": False}), {})


class GraphWiringTests(unittest.TestCase):
    def test_cache_nodes_only_when_enabled(self):
        with_cache = set(build_chat_graph(with_cache=True).get_graph().nodes)
        without = set(build_chat_graph(with_cache=False).get_graph().nodes)
        self.assertTrue({"cache_lookup", "cache_store"} <= with_cache)
        self.assertFalse({"cache_lookup", "cache_store"} & without)


if __name__ == "__main__":
    unittest.main()
