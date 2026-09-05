"""
Replace the previous generator with Qwen 2.5 3B Instruct.

Same file as components-Dinura/learnmate/chat_agent/generate.py and
integrated-backend/learnmate/chat_agent/generate.py. Only model_id changes.
Pair only with llama32-3b as judge. Never the same family in one process.
"""

MODEL_ID = 'qwen25-3b'
GGUF = 'qwen2.5-3b-instruct-q4_k_m.gguf'

from learnmate.chat_agent.generate import generate_node as live_generate_node


def generate_node(state):
    return live_generate_node({**state, "model_id": MODEL_ID})
