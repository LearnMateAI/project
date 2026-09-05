"""
Live retrieve node. Hybrid vs ANN is LEARNMATE_HYBRID_BM25 in the app;
this bake-off scores both in memory via eval_retrieval.py / eval_real_pdf.py.
"""

from learnmate.chat_agent.retrieve import retrieve_node

__all__ = ["retrieve_node"]
