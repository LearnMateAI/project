"""
Replace the previous judge with Granite 3.2 2B Instruct.

Same evaluate_node as integrated-backend. The bake-off injects this GGUF into
`Judge(llm=...)` so LEARNMATE_JUDGE_MODEL is not edited.
"""

MODEL_ID = 'granite-2b'
GGUF = 'ibm-granite_granite-3.2-2b-instruct-Q4_K_M.gguf'
PAIR_GENERATOR = 'qwen25-3b'

from learnmate.chat_agent.evaluate import evaluate_node

__all__ = ["evaluate_node", "MODEL_ID", "GGUF", "PAIR_GENERATOR"]
