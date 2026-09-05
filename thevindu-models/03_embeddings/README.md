# 03 — Embeddings

Drop-ins for live **all-MiniLM-L6-v2**. Stay 384-d. Switching requires a full re-ingest.

| Folder | Model |
|--------|--------|
| [minilm-l6](minilm-l6/) | all-MiniLM-L6-v2 (live baseline) |
| [bge-small](bge-small/) | BGE-small-en-v1.5 |
| [e5-small](e5-small/) | E5-small-v2 |

Each folder has `chat_agent/retrieve.py` pointing at the live retrieve node. Verdicts use the real PDF, not the toy fixture.
