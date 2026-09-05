"""
Do not load `gemma2-2b-judge` as the generator in the same process as this judge.

The live generate_node stays on `qwen25-3b`.
"""

PAIR_GENERATOR = 'qwen25-3b'

from learnmate.chat_agent.generate import generate_node

__all__ = ["generate_node", "PAIR_GENERATOR"]
