"""
Same job as components-Dinura/learnmate/chat_agent/generate.py and the fully-wired
copy in integrated-backend: write the reply.

This file is the bake-off entry point. It calls the live generate_node so a candidate
is tested against the prompts and retry shape the app actually ships — not a private
fork. `model_id` is the only replacement.
"""

from learnmate.chat_agent.generate import generate_node as live_generate_node


def generate_node(state, model_id=None):
    """Run the live generate node, optionally forcing a registry model_id."""
    if model_id:
        state = {**state, "model_id": model_id}
    return live_generate_node(state)
