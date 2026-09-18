"""Conversation list helpers: preview text and rename payload shape. No Mongo."""

from __future__ import annotations

import unittest

from pydantic import ValidationError

from app.schemas import RenameSessionRequest
from app.services.chat import preview_message


class PreviewMessageTests(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(preview_message(""), "")
        self.assertEqual(preview_message(None), "")

    def test_collapses_whitespace(self):
        self.assertEqual(preview_message("  hello\n\nworld  "), "hello world")

    def test_truncates_with_ellipsis(self):
        long = "a" * 100
        out = preview_message(long, limit=20)
        self.assertEqual(len(out), 20)
        self.assertTrue(out.endswith("…"))


class RenameSessionRequestTests(unittest.TestCase):
    def test_rejects_empty_title(self):
        with self.assertRaises(ValidationError):
            RenameSessionRequest(title="")

    def test_accepts_a_name(self):
        payload = RenameSessionRequest(title="Directors' duties")
        self.assertEqual(payload.title, "Directors' duties")


if __name__ == "__main__":
    unittest.main()
