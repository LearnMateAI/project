"""
Replace the previous embedder with E5-small-v2 for in-memory retrieve only.

Same retrieve contract as components-Dinura/learnmate/chat_agent/retrieve.py.
Does **not** write Qdrant. Mixed MiniLM/E5/BGE collections are undefined.
"""

HF_ID = 'intfloat/e5-small-v2'
MODEL_ID = 'e5-small'

from learnmate.chat_agent.retrieve import retrieve_node

__all__ = ["retrieve_node", "HF_ID", "MODEL_ID"]
