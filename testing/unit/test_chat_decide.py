"""U-08 — chat graph retry vs persist (`learnmate/chat_agent/routing.py`)."""

from learnmate.chat_agent.routing import decide


def _state(**overrides):
    base = {
        "passed": False,
        "attempt": 1,
        "max_attempts": 2,
        "verdict": {"score": 60},
        "threshold": 70,
        "critique": "Unsupported claim about section 99.",
        "verbose": False,
    }
    base.update(overrides)
    return base


def test_passed_always_persists():
    assert decide(_state(passed=True)) == "persist"


def test_budget_spent_persists_even_if_failed():
    assert decide(_state(attempt=2, max_attempts=2, passed=False)) == "persist"


def test_no_critique_skips_retry():
    assert decide(_state(critique="")) == "persist"


def test_failed_verdict_skips_retry():
    assert decide(_state(critique="the judge failed to return a verdict")) == "persist"


def test_hopeless_score_skips_retry():
    # default threshold 70, hopeless is < 45
    assert decide(_state(verdict={"score": 40}, critique="bad")) == "persist"


def test_actionable_near_miss_retries():
    assert decide(_state(verdict={"score": 55}, critique="Add a citation.")) == "generate"
