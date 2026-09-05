"""
Replace the previous embedder with BGE-small-en-v1.5 for in-memory retrieve only.

Same retrieve contract as components-Dinura/learnmate/chat_agent/retrieve.py.
Does **not** write Qdrant. Mixed MiniLM/E5/BGE collections are undefined.
"""

HF_ID = 'BAAI/bge-small-en-v1.5'
MODEL_ID = 'bge-small'

from learnmate.chat_agent.retrieve import retrieve_node

__all__ = ["retrieve_node", "HF_ID", "MODEL_ID"]
