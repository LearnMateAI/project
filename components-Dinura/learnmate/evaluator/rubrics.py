"""
The rubrics the judge grades against, one per kind of content.

Each is written to be decidable from the material given, and to name what should push a
score below 50 -- a 3B judge handed "rate the quality" returns 75 for everything, and a
grade that never varies cannot gate anything.

Each rubric deliberately leaves out what validators.py already checks mechanically. There
is no point spending 25 seconds of CPU asking a model to count to four.
"""

MCQ = """Judge these multiple-choice questions against the source passage.
- Answerability: each question must be answerable from the passage alone. A question needing outside knowledge scores below 50.
- Correctness: the marked correct answer must be the right one according to the passage. Any question whose marked answer is wrong or unsupported puts the whole set below 50.
- Distractors: the three wrong options should be plausible to someone who has not read carefully, but clearly wrong to someone who has. Options that are obviously absurd, or that are also defensible as correct, lower the score.
- Coverage: the questions should test different parts of the passage rather than asking the same fact repeatedly.
- Wording: a question that gives away its own answer, or that quotes the passage so completely that no understanding is needed, lowers the score."""

PRACTICE_QSN = """Judge these short-answer practice questions against the source passage.
- Correctness: each answer must be right according to the passage. One wrong answer puts the set below 50.
- Answerability: each question must be answerable from the passage alone. A question requiring outside knowledge scores below 50.
- Completeness: an answer that is correct but omits a qualifying condition the passage states is only partly right and should score in the middle.
- Non-triviality: a question whose answer is a single word lifted verbatim from the passage tests recall, not understanding, and lowers the score.
- Coverage: the questions should test different parts of the passage rather than circling one fact."""

KEYPOINTS = """Judge these key points against the source passage.
- Groundedness: every point must be supported by the passage. One invented point puts the set below 50.
- Significance: the points should capture what the passage treats as important, not incidental asides. Missing the central point is a serious fault even when every point listed is true.
- Distinctness: two points that say the same thing in different words count as one. Near-duplicates lower the score.
- Self-containment: each point must make sense read on its own, without a dangling "this" or "it" referring to another point.
- Granularity: points should be comparable in scope. A set mixing one sweeping statement with four trivia items scores poorly."""

SUMMARY = """Judge this summary against the source passage.
- Faithfulness: every claim must be supported by the passage. A single invented fact, name, number or date puts the summary below 50.
- Coverage: the main points of the passage should be present. A summary that captures only the opening and drops what follows scores poorly even when nothing in it is false.
- Proportion: emphasis should match the passage. Dwelling on an incidental detail while omitting the central point lowers the score.
- Concision: no padding, no restating the same point in different words, no meta-commentary such as "this passage discusses".
- Standalone sense: it should be readable by someone who has not seen the passage, with no dangling references."""

# The chat agent answers one of two ways per turn and the two are held to different
# standards. Which rubric applies is decided by whether context was actually retrieved,
# not by anything the reply says about itself.

CHAT_GROUNDED = """The reply answers the user's message using ONLY the retrieved context.
- Any claim not supported by the retrieved context is a hallucination: score below 50.
- The reply must actually answer the question, not merely restate the context.
- It must stay coherent with the conversation so far and resolve any follow-up reference.
- If the context genuinely does not contain the answer, saying so plainly is correct and scores well; inventing an answer does not."""

CHAT_GENERAL = """The reply answers the user's message from general knowledge; there is no source text to check it against.
- Relevance: it addresses what was actually asked, including any follow-up reference to earlier turns.
- Coherence: it does not contradict itself or the conversation so far.
- Informativeness: it is specific and useful, not padding, hedging, or a restatement of the question.
- Confident claims about niche facts, figures or dates that a small model is likely to get wrong should pull the score down."""

GENERIC = """Correctness, relevance to the given material, completeness, and clarity."""

RUBRICS = {
    "mcq": MCQ,
    "practice_qsn": PRACTICE_QSN,
    "keypoints": KEYPOINTS,
    "summary": SUMMARY,
    "chat_msg": CHAT_GENERAL,
    "generic": GENERIC,
}


def for_task(task: str, grounded: bool = False) -> str:
    """The rubric for a task. `grounded` selects the strict chat rubric."""
    if task == "chat_msg":
        return CHAT_GROUNDED if grounded else CHAT_GENERAL
    return RUBRICS.get(task, GENERIC)
