#  take input a generated keypoints and the source text and return a score from 1-100, along with input instruction to the model for regenerating the keypoints if the score is below a threshold.
"""
Rubric for generated key points.

Emptiness, count and exact duplicates are caught by validators.validate_keypoints() first.
This rubric judges groundedness, near-duplication and significance, which need reading.
"""

CRITERIA = """Judge these key points against the source passage.
- Groundedness: every point must be supported by the passage. One invented point puts the set below 50.
- Significance: the points should capture what the passage treats as important, not incidental asides. Missing the central point is a serious fault even when every point listed is true.
- Distinctness: two points that say the same thing in different words count as one. Near-duplicates lower the score.
- Self-containment: each point must make sense read on its own, without a dangling "this" or "it" referring to another point.
- Granularity: points should be comparable in scope. A set mixing one sweeping statement with four trivia items scores poorly."""
