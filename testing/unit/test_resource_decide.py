"""U-09 — resource graph retry vs persist (`learnmate/resource_agent/routing.py`)."""

from learnmate.resource_agent.routing import decide


def _state(**overrides):
    base = {
        "passed": False,
        "attempt": 1,
        "max_attempts": 2,
        "critique": "One option is blank.",
        "verbose": False,
    }
    base.update(overrides)
    return base


def test_passed_persists():
    assert decide(_state(passed=True)) == "persist"


def test_out_of_attempts_persists():
    assert decide(_state(attempt=2, max_attempts=2)) == "persist"


def test_failed_with_budget_left_regenerates():
    assert decide(_state(attempt=1, max_attempts=2, passed=False)) == "generate"
