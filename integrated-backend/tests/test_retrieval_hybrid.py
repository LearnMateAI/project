"""
Unit tests for server-side hybrid retrieval (learnmate/retrieval).

No Mongo, Qdrant or models: the analyzer and fusion are pure functions, the mode decision
takes a patched reranker, and the Qdrant query is checked against a fake client that only
records what it was asked.
"""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest import mock

from langchain_core.documents import Document

from learnmate import config
from learnmate.retrieval import retriever
from learnmate.retrieval.analyzer import analyze, display_tokens, stem
from learnmate.retrieval.fusion import dbsf_fuse, rrf_fuse
from learnmate.retrieval.sparse import bm25_doc_vector, bm25_query_vector, term_id
from learnmate.storage.qdrant_vectors import QdrantVectorStore, UnsupportedStrategy


class PorterStemmerTests(unittest.TestCase):
    # From Martin Porter's published vocabulary/output pairs.
    CASES = {
        "caresses": "caress", "ponies": "poni", "ties": "ti", "caress": "caress",
        "cats": "cat", "feed": "feed", "agreed": "agre", "plastered": "plaster",
        "bled": "bled", "motoring": "motor", "sing": "sing", "conflated": "conflat",
        "troubled": "troubl", "sized": "size", "hopping": "hop", "tanned": "tan",
        "falling": "fall", "hissing": "hiss", "fizzed": "fizz", "failing": "fail",
        "filing": "file", "happy": "happi", "sky": "sky", "relational": "relat",
        "conditional": "condit", "rational": "ration", "valenci": "valenc",
        "digitizer": "digit", "conformabli": "conform", "radicalli": "radic",
        "differentli": "differ", "vileli": "vile", "analogousli": "analog",
        "vietnamization": "vietnam", "predication": "predic", "operator": "oper",
        "feudalism": "feudal", "decisiveness": "decis", "hopefulness": "hope",
        "callousness": "callous", "formaliti": "formal", "sensitiviti": "sensit",
        "sensibiliti": "sensibl", "triplicate": "triplic", "formative": "form",
        "formalize": "formal", "electriciti": "electr", "electrical": "electr",
        "hopeful": "hope", "goodness": "good", "revival": "reviv", "allowance": "allow",
        "inference": "infer", "airliner": "airlin", "gyroscopic": "gyroscop",
        "adjustable": "adjust", "defensible": "defens", "irritant": "irrit",
        "replacement": "replac", "adjustment": "adjust", "dependent": "depend",
        "adoption": "adopt", "homologou": "homolog", "communism": "commun",
        "activate": "activ", "angulariti": "angular", "homologous": "homolog",
        "effective": "effect", "bowdlerize": "bowdler", "probate": "probat",
        "rate": "rate", "cease": "ceas", "controll": "control", "roll": "roll",
        "generalizations": "gener", "oscillators": "oscil",
    }

    def test_reference_vocabulary(self):
        wrong = {word: (stem(word), expected) for word, expected in self.CASES.items()
                 if stem(word) != expected}
        self.assertEqual(wrong, {})

    def test_numbers_and_short_words_untouched(self):
        self.assertEqual(stem("1978"), "1978")
        self.assertEqual(stem("is"), "is")


class AnalyzerTests(unittest.TestCase):
    def test_stopwords_dropped_and_morphology_folded(self):
        self.assertEqual(analyze("The duties of the directors"), ["duti", "director"])
        self.assertEqual(analyze("duty"), analyze("duties"))

    def test_accents_and_case_fold(self):
        self.assertEqual(analyze("Café"), analyze("cafe"))

    def test_section_numbers_survive(self):
        self.assertIn("12", analyze("Section 12(3) applies"))

    def test_display_tokens_are_not_stemmed(self):
        self.assertEqual(display_tokens("Fiduciary duties"), ["fiduciary", "duties"])


class SparseVectorTests(unittest.TestCase):
    def test_term_id_is_stable_31_bit(self):
        first = term_id("director")
        self.assertEqual(first, term_id("director"))
        self.assertLess(first, 2 ** 31)
        self.assertNotEqual(first, term_id("duti"))

    def test_query_vector_is_unit_weight_per_distinct_term(self):
        indices, values = bm25_query_vector("trust deed and trust")
        self.assertEqual(len(indices), 2)
        self.assertEqual(values, [1.0, 1.0])
        self.assertEqual(indices, sorted(indices))

    def test_term_frequency_saturates(self):
        _, one = bm25_doc_vector("estoppel", 1.2, 0.75, 1.0)
        _, five = bm25_doc_vector("estoppel " * 5, 1.2, 0.75, 5.0)
        self.assertGreater(five[0], one[0])
        # Bounded by k1 + 1 however often the term repeats.
        self.assertLess(five[0], 2.2)

    def test_longer_chunks_are_normalised_down(self):
        def weight(text):
            return dict(zip(*bm25_doc_vector(text, 1.2, 0.75, 10.0)))[term_id("estoppel")]

        self.assertGreater(weight("estoppel doctrine"),
                           weight("estoppel doctrine " + "filler words " * 20))

    def test_empty_text(self):
        self.assertEqual(bm25_doc_vector("the of and", 1.2, 0.75, 10.0), ([], []))
        self.assertEqual(bm25_query_vector("what is it"), ([], []))


class FusionTests(unittest.TestCase):
    def test_rrf_hand_example(self):
        fused = dict(rrf_fuse([["a", "b", "c"], ["b", "d"]], k=60))
        self.assertAlmostEqual(fused["b"], 1 / 62 + 1 / 61)
        self.assertAlmostEqual(fused["a"], 1 / 61)
        self.assertAlmostEqual(fused["d"], 1 / 62)
        self.assertEqual(rrf_fuse([["a", "b", "c"], ["b", "d"]], k=60)[0][0], "b")

    def test_rrf_ties_break_on_first_appearance(self):
        order = [key for key, _ in rrf_fuse([["x"], ["y"]], k=60)]
        self.assertEqual(order, ["x", "y"])

    def test_rrf_weights(self):
        fused = rrf_fuse([["a"], ["b"]], k=60, weights=[1.0, 2.0])
        self.assertEqual(fused[0][0], "b")

    def test_dbsf_normalises_each_list(self):
        fused = dict(dbsf_fuse([[("a", 0.9), ("b", 0.1)], [("b", 30.0), ("c", 10.0)]]))
        # b is bottom of one list and top of the other; a and c are each top/bottom once.
        self.assertGreater(fused["b"], fused["c"])
        self.assertTrue(all(0.0 <= v <= 2.0 for v in fused.values()))

    def test_dbsf_single_result(self):
        self.assertEqual(dbsf_fuse([[("a", 3.0)]]), [("a", 0.5)])


def _doc(page, chunk, text="text"):
    return Document(page_content=text, metadata={"page_number": page, "chunk_index": chunk})


class DecideTests(unittest.TestCase):
    def _result(self, hits):
        return retriever.RetrievalResult(hits=hits, strategy="rrf", requested="rrf")

    def test_rerank_basis_keeps_strong_chunks_and_decides_pdf(self):
        hits = [retriever.Hit(_doc(1, 0), 0.03), retriever.Hit(_doc(2, 0), 0.02),
                retriever.Hit(_doc(3, 0), 0.01)]
        ranked = [(hits[1].doc, 0.95), (hits[0].doc, 0.7), (hits[2].doc, 0.01)]
        with mock.patch.object(retriever.reranker, "rerank", return_value=ranked):
            decision = retriever.decide("q", self._result(hits), use_reranker=True)
        self.assertEqual(decision.mode, "pdf")
        self.assertEqual(decision.basis, "rerank")
        self.assertEqual([d.metadata["page_number"] for d in decision.contexts], [2, 1])
        self.assertEqual(decision.nearest["page"], 2)

    def test_weak_best_is_kept_and_mode_is_general(self):
        hits = [retriever.Hit(_doc(4, 1), 0.03)]
        with mock.patch.object(retriever.reranker, "rerank",
                               return_value=[(hits[0].doc, 0.2)]):
            decision = retriever.decide("q", self._result(hits), use_reranker=True)
        self.assertEqual(decision.mode, "general")
        self.assertEqual(len(decision.contexts), 1)
        self.assertEqual(decision.nearest, {"page": 4, "chunk_index": 1, "score": 0.2})

    def test_cosine_fallback_ignores_fused_rank_scores(self):
        # A fused score of 0.03 is a rank, not a similarity; the cosine decides.
        hits = [retriever.Hit(_doc(1, 0), 0.033, dense_cos=0.10),
                retriever.Hit(_doc(2, 0), 0.032, dense_cos=0.60)]
        with mock.patch.object(retriever.reranker, "rerank", return_value=None):
            decision = retriever.decide("q", self._result(hits), use_reranker=True)
        self.assertEqual(decision.basis, "cosine")
        self.assertEqual(decision.mode, "pdf")
        self.assertAlmostEqual(decision.top_score, 0.60)
        self.assertEqual(decision.nearest["page"], 2)

    def test_no_hits_is_general(self):
        decision = retriever.decide("q", self._result([]), use_reranker=False)
        self.assertEqual((decision.mode, decision.contexts), ("general", []))


class SearchFallbackTests(unittest.TestCase):
    def setUp(self):
        retriever._WARNED.clear()

    def test_unsupported_strategy_falls_back_to_legacy(self):
        store = mock.Mock()
        store.supports.return_value = False
        legacy_hit = retriever.Hit(_doc(7, 0), 0.8, source="ann")
        with mock.patch.object(retriever, "get_vector_store", return_value=store), \
                mock.patch.object(retriever, "_legacy", return_value=([legacy_hit], None)):
            result = retriever.search("q", "doc", k=5, strategy="rrf")
        self.assertEqual(result.strategy, "legacy")
        self.assertEqual(result.requested, "rrf")
        self.assertEqual(result.hits, [legacy_hit])

    def test_unknown_strategy_falls_back(self):
        with mock.patch.object(retriever, "_legacy", return_value=([], None)):
            result = retriever.search("q", "doc", k=5, strategy="nonsense")
        self.assertEqual(result.strategy, "legacy")


class _FakeClient:
    """Records query_points calls and answers with two canned points."""

    def __init__(self):
        self.calls = []

    def query_points(self, **kwargs):
        self.calls.append(kwargs)
        points = [
            SimpleNamespace(id="p1", score=0.5,
                            payload={"doc_id": "d", "page_number": 3, "chunk_index": 0,
                                     "text": "a"},
                            vector={"dense": [1.0, 0.0]}),
            SimpleNamespace(id="p2", score=0.4,
                            payload={"doc_id": "d", "page_number": 5, "chunk_index": 1,
                                     "text": "b"},
                            vector={"dense": [0.0, 1.0]}),
        ]
        return SimpleNamespace(points=points)


class QdrantQueryBuildTests(unittest.TestCase):
    def _store(self, sparse=("bm25",)):
        store = QdrantVectorStore(embedding=mock.Mock(), url="http://unused")
        store._client = _FakeClient()
        store._collection_ready = True
        store.schema = "v2"
        store._sparse_names = frozenset(sparse)
        return store

    def test_rrf_filters_every_prefetch_and_uses_named_vectors(self):
        from qdrant_client import models

        store = self._store()
        rows = store.query("rrf", "directors duties", [0.6, 0.8], k=5, doc_id="d")
        call = store.client.calls[0]
        self.assertEqual(len(call["prefetch"]), 2)
        for prefetch in call["prefetch"]:
            self.assertIsNotNone(prefetch.filter)
            self.assertEqual(prefetch.limit, max(config.HYBRID_PREFETCH, 5))
        self.assertEqual([p.using for p in call["prefetch"]], ["dense", "bm25"])
        self.assertIsInstance(call["prefetch"][1].query, models.SparseVector)
        self.assertIsNotNone(call["query_filter"])
        self.assertEqual(call["with_vectors"], ["dense"])
        if config.RRF_K > 0:
            self.assertIsInstance(call["query"], models.RrfQuery)
            self.assertEqual(call["query"].rrf.k, config.RRF_K)
        # dense_cos is recomputed from the returned vectors, not taken from the rank score.
        self.assertAlmostEqual(rows[0][2], 0.6)
        self.assertAlmostEqual(rows[1][2], 0.8)
        self.assertEqual(rows[0][0].metadata["page_number"], 3)

    def test_dbsf_uses_fusion_query(self):
        from qdrant_client import models

        store = self._store()
        store.query("dbsf", "directors", [1.0, 0.0], k=3, doc_id="d")
        query = store.client.calls[0]["query"]
        self.assertIsInstance(query, models.FusionQuery)
        self.assertEqual(query.fusion, models.Fusion.DBSF)

    def test_stopword_only_query_drops_sparse_branch(self):
        store = self._store()
        store.query("rrf", "what is it", [1.0, 0.0], k=3, doc_id="d")
        self.assertEqual(len(store.client.calls[0]["prefetch"]), 1)
        self.assertEqual(store.query("bm25", "what is it", [1.0, 0.0], k=3), [])

    def test_splade_needs_its_vector(self):
        store = self._store()
        self.assertFalse(store.supports("splade"))
        with self.assertRaises(UnsupportedStrategy):
            store.query("splade", "x", [1.0], k=1)

    def test_legacy_collection_cannot_fuse(self):
        store = self._store()
        store.schema = "legacy"
        self.assertTrue(store.supports("dense"))
        self.assertFalse(store.supports("rrf"))

    def test_schema_detection(self):
        store = QdrantVectorStore(embedding=mock.Mock(), url="http://unused")
        store._detect_schema(SimpleNamespace(vectors={"dense": object()},
                                             sparse_vectors={"bm25": object()}))
        self.assertEqual((store.schema, store._sparse_names), ("v2", frozenset({"bm25"})))
        store._detect_schema(SimpleNamespace(vectors=object(),
                                             sparse_vectors={"sparse": object()}))
        self.assertEqual((store.schema, store._hybrid), ("legacy", True))


if __name__ == "__main__":
    unittest.main()
