"""U-07 — summary / keypoints / practice-question gates (`text_rules.py`)."""

from learnmate.evaluator.text_rules import (
    validate_keypoints,
    validate_practice_qsn,
    validate_summary,
)


def test_practice_empty_set():
    ok, reasons = validate_practice_qsn([])
    assert ok is False
    assert "no questions" in reasons[0]


def test_practice_rejects_empty_and_restated_answer():
    ok, reasons = validate_practice_qsn([
        {"question": "What is consideration?", "answer": ""},
        {"question": "Define offer", "answer": "Define offer"},
    ])
    assert ok is False
    assert any("empty answer" in r for r in reasons)
    assert any("restates" in r for r in reasons)


def test_practice_happy_path():
    ok, reasons = validate_practice_qsn([
        {"question": "What is consideration?", "answer": "Something of value in a contract."},
    ])
    assert ok is True
    assert reasons == []


def test_keypoints_minimum_and_duplicates():
    ok, _ = validate_keypoints(["only one"])
    assert ok is False
    ok, reasons = validate_keypoints(["Duty of care.", "duty of care"])
    assert ok is False
    assert any("duplicates" in r for r in reasons)


def test_keypoints_happy_path():
    ok, reasons = validate_keypoints(["Directors owe duties.", "Those duties are fiduciary."])
    assert ok is True
    assert reasons == []


def test_summary_too_short_or_empty():
    ok, _ = validate_summary("")
    assert ok is False
    ok, reasons = validate_summary("Too short.")
    assert ok is False
    assert any("too short" in r for r in reasons)


def test_summary_long_enough():
    text = "This summary is long enough to stand in for a page of source material. " * 2
    ok, reasons = validate_summary(text)
    assert ok is True
    assert reasons == []
