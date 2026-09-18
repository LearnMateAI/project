"""U-20 — MCQ difficulty tier resolution (`learnmate/resource_agent/mcq.py`).

Pure string function: `GenerateRequest.difficulty` already validates the pattern
(easy/medium/hard) at the API boundary (test_schemas.py); this is the second line of
defence inside the resource agent itself, reached even if a caller bypasses the schema.
"""

from learnmate.resource_agent.mcq import resolve_difficulty


def test_known_tiers_pass_through():
    assert resolve_difficulty("easy") == "easy"
    assert resolve_difficulty("medium") == "medium"
    assert resolve_difficulty("hard") == "hard"


def test_none_defaults_to_medium():
    assert resolve_difficulty(None) == "medium"


def test_blank_and_unknown_values_default_to_medium():
    assert resolve_difficulty("") == "medium"
    assert resolve_difficulty("   ") == "medium"
    assert resolve_difficulty("impossible") == "medium"


def test_is_case_and_whitespace_insensitive():
    assert resolve_difficulty(" HARD ") == "hard"
    assert resolve_difficulty("Easy") == "easy"
