# Take input a practice question and the generated answer, and return a score from 1-100, along with input instruction to the model for regenerating the answer if the score is below a threshold.
"""
Rubric for generated short-answer practice questions.

Empty fields and answers that merely restate the question are caught by
validators.validate_practice_qsn() first. This rubric judges whether the answers are
actually correct against the source.
"""

CRITERIA = """Judge these short-answer practice questions against the source passage.
- Correctness: each answer must be right according to the passage. One wrong answer puts the set below 50.
- Answerability: each question must be answerable from the passage alone. A question requiring outside knowledge scores below 50.
- Completeness: an answer that is correct but omits a qualifying condition the passage states is only partly right and should score in the middle.
- Non-triviality: a question whose answer is a single word lifted verbatim from the passage tests recall, not understanding, and lowers the score.
- Coverage: the questions should test different parts of the passage rather than circling one fact."""
