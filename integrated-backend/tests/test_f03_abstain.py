"""
F-03: document-bound chat with weak retrieval must abstain, not invent.

No GGUF, Mongo, or Qdrant. generate_node is exercised with get_generator_llm patched
so a regression that falls through to GENERAL_SYSTEM fails the test by calling the mock.
"""

from __future__ import annotations

import unittest
from unittest.mock import patch

from langchain_core.documents import Document

from learnmate.chat_agent.generate import generate_node
from learnmate.chat_agent.prompts import (
    ABSTAIN_STEM,
    abstain_reply,
    should_abstain,
)


def _state(**overrides):
    base = {
        "query": "What is the capital of France?",
        "max_attempts": 2,
        "attempt": 0,
        "verbose": False,
        "contexts": [],
        "top_score": 0.03,
        "mode": "general",
        "history": [],
    }
    base.update(overrides)
    return base


class ShouldAbstainTests(unittest.TestCase):
    def test_document_bound_empty_contexts_abstains(self):
        self.assertTrue(should_abstain(_state(doc_id="doc-1")))

    def test_unbound_cli_does_not_abstain(self):
        self.assertFalse(should_abstain(_state(doc_id=None)))

    def test_pdf_mode_with_chunks_does_not_abstain(self):
        chunk = Document(page_content="Directors owe fiduciary duties.",
                         metadata={"page_number": 3})
        self.assertFalse(should_abstain(_state(doc_id="doc-1", contexts=[chunk])))


class AbstainReplyTests(unittest.TestCase):
    def test_stem_and_score(self):
        text = abstain_reply(0.031)
        self.assertTrue(text.startswith(ABSTAIN_STEM))
        self.assertIn("0.03", text)
        self.assertNotIn("France", text)
        self.assertNotIn("Paris", text)


class GenerateNodeAbstainTests(unittest.TestCase):
    def test_document_bound_does_not_call_the_llm(self):
        with patch("learnmate.chat_agent.generate.get_generator_llm") as llm:
            out = generate_node(_state(doc_id="doc-1"))
        llm.assert_not_called()
        self.assertTrue(out["reply"].startswith(ABSTAIN_STEM))
        self.assertIn("0.03", out["reply"])
        self.assertEqual(out["attempt"], 1)

    def test_unbound_still_calls_the_generator(self):
        class _Chunk:
            content = "Paris is the capital of France."

        class _Fake:
            def stream(self, *args, **kwargs):
                yield _Chunk()

        with patch("learnmate.chat_agent.generate.get_generator_llm",
                   return_value=_Fake()) as llm:
            out = generate_node(_state(doc_id=None))
        llm.assert_called_once()
        self.assertIn("Paris", out["reply"])


if __name__ == "__main__":
    unittest.main()
