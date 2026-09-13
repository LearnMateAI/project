"""U-06 — MCQ structural gate (`learnmate/evaluator/mcq_rules.py`)."""

from learnmate.evaluator.mcq_rules import validate_mcq, validate_mcq_set


def _q(stem, options, correct):
    return {"question": stem, "options": options, "correct_answer": correct}


GOOD = ["Alpha", "Bravo", "Charlie", "Delta"]


def test_valid_question_passes():
    ok, reasons = validate_mcq(_q("Which is first?", GOOD, "Alpha"))
    assert ok is True
    assert reasons == []


def test_wrong_option_count_fails_fast():
    ok, reasons = validate_mcq(_q("Q?", ["A", "B", "C"], "A"))
    assert ok is False
    assert any("instead of exactly 4" in r for r in reasons)


def test_blank_and_duplicate_options():
    ok, _ = validate_mcq(_q("Q?", ["A", "B", "C", ""], "A"))
    assert ok is False
    ok, _ = validate_mcq(_q("Q?", ["A", "A", "B", "C"], "A"))
    assert ok is False


def test_correct_answer_must_be_an_option():
    ok, reasons = validate_mcq(_q("Q?", GOOD, "Echo"))
    assert ok is False
    assert any("not one of its options" in r for r in reasons)


def test_all_of_the_above_is_rejected():
    opts = ["A", "B", "C", "All of the above"]
    ok, reasons = validate_mcq(_q("Q?", opts, "A"))
    assert ok is False
    assert any("all/none of the above" in r for r in reasons)


def test_empty_set_fails():
    ok, reasons = validate_mcq_set([])
    assert ok is False
    assert "no questions" in reasons[0]


def test_position_bias_across_four_questions():
    items = [_q(f"Q{i}?", GOOD, "Alpha") for i in range(4)]
    ok, reasons = validate_mcq_set(items)
    assert ok is False
    assert any("position" in r for r in reasons)


def test_length_bias_when_correct_always_longest():
    items = []
    for i in range(4):
        opts = ["no", "nope", "nah", "this is the very long correct option"]
        items.append(_q(f"Question {i} about law?", opts, opts[-1]))
    ok, reasons = validate_mcq_set(items)
    assert ok is False
    assert any("longest" in r for r in reasons)


def test_duplicate_stems():
    items = [
        _q("Same stem?", GOOD, "Alpha"),
        _q("Same stem?", ["W", "X", "Y", "Z"], "W"),
    ]
    ok, reasons = validate_mcq_set(items)
    assert ok is False
    assert any("identical" in r for r in reasons)
