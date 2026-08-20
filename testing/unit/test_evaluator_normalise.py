"""U-05 — comparison-safe text (`learnmate/evaluator/normalise.py`)."""

from learnmate.evaluator.normalise import norm


def test_norm_collapses_case_space_and_trailing_punctuation():
    assert norm("  The Cabinet. ") == "the cabinet"
    assert norm("the cabinet") == norm("The Cabinet!")
    assert norm(None) == ""
    assert norm("A   B") == "a b"
