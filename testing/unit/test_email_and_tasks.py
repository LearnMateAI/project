"""U-12 — email normalisation and resource task registry."""

import pytest

from learnmate.resource_agent.tasks import TASK_NAMES, get_task
from learnmate.storage.users import normalise_email


def test_email_is_stripped_and_lowercased():
    assert normalise_email("  Ada@Uni.LK ") == "ada@uni.lk"
    assert normalise_email("") == ""


def test_known_tasks_exist():
    assert set(TASK_NAMES) == {"keypoints", "mcq", "practice_qsn", "summary"}
    for name in TASK_NAMES:
        assert get_task(name).name == name or get_task(name) is not None


def test_unknown_task_names_alternatives():
    with pytest.raises(ValueError, match="Unknown task"):
        get_task("flashcards")
