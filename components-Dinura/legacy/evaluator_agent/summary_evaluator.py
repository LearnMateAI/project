# Take input a generated summary and the source text and return a score from 1-100, along with input instruction to the model for regenerating the summary if the score is below a threshold.
"""
Rubric for generated summaries.

Emptiness and length are checked by validators.validate_summary() first; this rubric judges
faithfulness and coverage, which code cannot decide.
"""

CRITERIA = """Judge this summary against the source passage.
- Faithfulness: every claim must be supported by the passage. A single invented fact, name, number or date puts the summary below 50.
- Coverage: the main points of the passage should be present. A summary that captures only the opening and drops what follows scores poorly even when nothing in it is false.
- Proportion: emphasis should match the passage. Dwelling on an incidental detail while omitting the central point lowers the score.
- Concision: no padding, no restating the same point in different words, no meta-commentary such as "this passage discusses".
- Standalone sense: it should be readable by someone who has not seen the passage, with no dangling references."""
