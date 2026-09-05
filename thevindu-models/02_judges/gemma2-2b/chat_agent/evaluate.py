"""
Replace the previous judge with Gemma 2 2B Instruct (judge role).

Same evaluate_node as integrated-backend. The bake-off injects this GGUF into
`Judge(llm=...)` so LEARNMATE_JUDGE_MODEL is not edited.
"""

MODEL_ID = 'gemma2-2b-judge'
GGUF = 'gemma-2-2b-it-Q4_K_M.gguf'
PAIR_GENERATOR = 'qwen25-3b'

from learnmate.chat_agent.evaluate import evaluate_node

__all__ = ["evaluate_node", "MODEL_ID", "GGUF", "PAIR_GENERATOR"]
