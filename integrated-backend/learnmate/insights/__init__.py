"""
Class insights mined from the chat log: where in a shared document students get stuck.

    aggregate.py   MongoDB pipelines: questions paired with answers, per-page counts
    cluster.py     questions -> topics (MiniLM + HDBSCAN + c-TF-IDF)
    confusion.py   the confusion score and k-anonymity, as pure functions
    service.py     compute, cache in `doc_insights`, return
"""

from .service import compute_heatmap, get_heatmap

__all__ = ["compute_heatmap", "get_heatmap"]
