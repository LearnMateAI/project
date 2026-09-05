"""
Replace the previous generator with Gemma 2 2B Instruct.

Same file as components-Dinura/learnmate/chat_agent/generate.py and
integrated-backend/learnmate/chat_agent/generate.py. Only model_id changes.
Pair only with llama32-3b as judge. Never the same family in one process.
"""

MODEL_ID = 'gemma2-2b'
GGUF = 'gemma-2-2b-it-Q4_K_M.gguf'

from learnmate.chat_agent.generate import generate_node as live_generate_node


def generate_node(state):
    return live_generate_node({**state, "model_id": MODEL_ID})
