"""
Same job as components-Dinura/learnmate/chat_agent/evaluate.py.

The live evaluate_node logs to Mongo. The bake-off calls Judge.judge_chat_reply
directly so a laptop eval does not need Docker and does not write production
collections. The rubric, prompt, and fail-closed verdict are still the live ones.
"""

from learnmate.chat_agent.evaluate import evaluate_node as live_evaluate_node
from learnmate.evaluator.judge import Judge


def evaluate_node(state):
    """Live evaluate_node (needs storage). Prefer judge_reply() for offline scoring."""
    return live_evaluate_node(state)


def judge_reply(query, reply, contexts=None, threshold=70, llm=None):
    """Gate 2 only, live Judge class, optional injected candidate llm."""
    return Judge(llm=llm, threshold=threshold).judge_chat_reply(
        query, reply, contexts=contexts, threshold=threshold,
    )
