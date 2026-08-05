# Take input a multiple choice question and the generated answer, and return a score from 1-100, along with input instruction to the model for regenerating the answer if the score is below a threshold.
"""
Rubric for generated multiple-choice questions.

Structural faults -- wrong option count, correct_answer missing from the options, duplicate
distractors, position or length bias -- are caught by validators.validate_mcq_set() before
this rubric is ever used, so it only has to judge what code cannot: whether the question is
genuinely answerable from the source and whether the marked answer is actually right.
"""

CRITERIA = """Judge these multiple-choice questions against the source passage.
- Answerability: each question must be answerable from the passage alone. A question needing outside knowledge scores below 50.
- Correctness: the marked correct answer must be the right one according to the passage. Any question whose marked answer is wrong or unsupported puts the whole set below 50.
- Distractors: the three wrong options should be plausible to someone who has not read carefully, but clearly wrong to someone who has. Options that are obviously absurd, or that are also defensible as correct, lower the score.
- Coverage: the questions should test different parts of the passage rather than asking the same fact repeatedly.
- Wording: a question that gives away its own answer, or that quotes the passage so completely that no understanding is needed, lowers the score."""
