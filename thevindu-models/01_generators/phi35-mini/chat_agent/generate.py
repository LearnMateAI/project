"""
Replace the previous generator with Phi-3.5 Mini Instruct.

Same file as components-Dinura/learnmate/chat_agent/generate.py and
integrated-backend/learnmate/chat_agent/generate.py. Only model_id changes.
Pair only with llama32-3b as judge. Never the same family in one process.
"""

MODEL_ID = 'phi35-mini'
GGUF = 'Phi-3.5-mini-instruct-Q4_K_M.gguf'

from learnmate.chat_agent.generate import generate_node as live_generate_node


def generate_node(state):
    return live_generate_node({**state, "model_id": MODEL_ID})
