# Take input a chat context input message + reply pair and return a score from 1-100, along with input instruction to the model for regenerating the reply if the score is below a threshold.
# The score is based on the quality of the reply in terms of relevance, coherence, and informativeness.
# The instruction for regeneration should be clear and specific, guiding the model to improve the reply while maintaining the context of the conversation.
"""
Evaluator for chat-agent/ replies.

It grades exactly what that agent's LLM was given and what it produced:

    input  -> the user's message, the rolling history from ChatSession, and (in PDF mode)
              the chunks DocumentRetriever returned
    output -> the answer string from AnswerGenerator / GeneralAnswerGenerator

chat.py picks one of two generators per turn, and they are held to different standards:

    PDF mode      (AnswerGenerator, retrieval score above RELEVANCE_THRESHOLD)
                  -> told to answer "strictly based on the provided context", so anything
                     the retrieved chunks do not support is a hallucination and fails.
    General mode  (GeneralAnswerGenerator, retrieval scored too low)
                  -> answers from general knowledge, so there is nothing to check it
                     against; only relevance, coherence and informativeness are judged.

Passing `contexts` is what selects the strict rubric.
"""

from agent import DEFAULT_THRESHOLD

GROUNDED_CRITERIA = """The reply answers the user's message using ONLY the retrieved context.
- Any claim not supported by the retrieved context is a hallucination: score below 50.
- The reply must actually answer the question, not merely restate the context.
- It must stay coherent with the conversation so far and resolve any follow-up reference.
- If the context genuinely does not contain the answer, saying so plainly is correct and scores well; inventing an answer does not."""

GENERAL_CRITERIA = """The reply answers the user's message from general knowledge; there is no source text to check it against.
- Relevance: it addresses what was actually asked, including any follow-up reference to earlier turns.
- Coherence: it does not contradict itself or the conversation so far.
- Informativeness: it is specific and useful, not padding, hedging, or a restatement of the question.
- Confident claims about niche facts, figures or dates that a small model is likely to get wrong should pull the score down."""

# chat-agent's generators swallow failures into this string instead of raising.
GENERATOR_ERROR_PREFIX = "Error generating answer locally:"


def _format_history(history: list) -> str:
    """Render ChatSession.get_history() turns for the judge."""
    if not history:
        return ""
    lines = [f"{turn.get('role', 'user').capitalize()}: {turn.get('content', '')}" for turn in history]
    return "CONVERSATION SO FAR:\n" + "\n".join(lines)


def _format_contexts(contexts: list) -> str:
    """Render DocumentRetriever.retrieve() hits the same way AnswerGenerator does."""
    if not contexts:
        return ""
    chunks = [f"Page {c.get('page_number', 'N/A')}: {c.get('text', '')}" for c in contexts]
    return "RETRIEVED CONTEXT (the reply may not go beyond this):\n" + "\n\n".join(chunks)


def evaluate_reply(llm, query: str, reply: str, contexts: list = None, history: list = None,
                   threshold: int = DEFAULT_THRESHOLD) -> dict:
    """
    Score one chat turn.

    query     -- the user's message
    reply     -- what the chat agent's LLM answered
    contexts  -- DocumentRetriever hits if the turn ran in PDF mode; None for general mode
    history   -- prior turns from ChatSession, for judging follow-up coherence

    Returns the standard verdict dict from EvaluatorLLM.judge():
        {task, score, passed, reasoning, regeneration_instruction, threshold}
    """
    reply = (reply or "").strip()

    # Don't burn ~25s of CPU judging a generator crash; it is a failure by definition.
    if not reply or reply.startswith(GENERATOR_ERROR_PREFIX):
        return {
            "task": "chat_msg",
            "score": 1,
            "passed": False,
            "reasoning": "The chat agent returned an error or an empty reply.",
            "regeneration_instruction": "Regenerate the reply; the previous attempt failed to produce an answer.",
            "threshold": threshold,
        }

    blocks = [
        _format_history(history),
        _format_contexts(contexts),
        f"USER MESSAGE THE REPLY MUST ANSWER:\n{query}",
    ]
    source = "\n\n".join(block for block in blocks if block)

    criteria = GROUNDED_CRITERIA if contexts else GENERAL_CRITERIA

    return llm.judge("chat_msg", reply, source=source, criteria=criteria, threshold=threshold)


def evaluate(llm, generated: str, source: str = None, threshold: int = DEFAULT_THRESHOLD) -> dict:
    """
    Entry point main.py calls: `generated` is the reply, `source` the chat context blob.

    The CLI hands over free-form text, so PDF and general mode cannot be told apart here
    and the reply is graded on the general rubric. Call evaluate_reply() from chat.py
    instead to get the strict grounded check.
    """
    return llm.judge("chat_msg", generated, source=source, criteria=GENERAL_CRITERIA,
                     threshold=threshold)
