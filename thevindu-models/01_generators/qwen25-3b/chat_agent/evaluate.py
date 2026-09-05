"""
Evaluate a Qwen 2.5 3B Instruct reply with the live judge (llama32-3b).

Does not load this GGUF as judge. Same evaluate_node as the fully-wired app.
"""

PAIR_JUDGE = 'llama32-3b'

from learnmate.chat_agent.evaluate import evaluate_node
from learnmate.evaluator.judge import Judge

__all__ = ["evaluate_node", "Judge", "PAIR_JUDGE"]
