"""
Replace the previous judge with Llama 3.2 3B Instruct.

Same evaluate_node as integrated-backend. The bake-off injects this GGUF into
`Judge(llm=...)` so LEARNMATE_JUDGE_MODEL is not edited.
"""

MODEL_ID = 'llama32-3b'
GGUF = 'Llama-3.2-3B-Instruct-Q4_K_M.gguf'
PAIR_GENERATOR = 'qwen25-3b'

from learnmate.chat_agent.evaluate import evaluate_node

__all__ = ["evaluate_node", "MODEL_ID", "GGUF", "PAIR_GENERATOR"]
