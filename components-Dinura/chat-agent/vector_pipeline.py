import os
import sys

from embedding_generator import EmbeddingGenerator
from qdrant_db import QdrantManager

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "ingestion"))
from chunker import chunk_pages

class DocumentChunk:
    """A simple wrapper to format data for Qdrant storage."""
    def __init__(self, content, metadata):
        self.content = content
        self.metadata = metadata

def process_and_store_embeddings(formatted_data: list, pdf_path: str, collection_name: str = "knowledge_base",
                                 db_path: str = "./qdrant_data"):
    """
    Takes formatted dictionary data, generates embeddings, and stores them in Qdrant.

    Pages are split into sub-page chunks first (see ingestion/chunker.py): one vector per
    page averages every provision on that page together, which lets a contents page
    out-rank the article a question is actually about.
    """
    print("\n--- Starting Vectorization & Storage ---")

    # 1. Split pages into passages, then wrap them in the structure QdrantManager expects
    chunks = chunk_pages(formatted_data)
    print(f"[*] {len(formatted_data)} pages -> {len(chunks)} chunks")

    chunks_for_qdrant = [
        DocumentChunk(
            content=item["text"],
            metadata={
                "page_index": item["page_index"],
                "page_number": item["page_number"],
                "chunk_index": item["chunk_index"],
                "source": pdf_path
            }
        )
        for item in chunks
    ]

    if not chunks_for_qdrant:
        print("[!] No substantive text found; nothing to store.")
        return

    # 2. Generate Embeddings
    embedder = EmbeddingGenerator()
    texts_to_embed = [chunk.content for chunk in chunks_for_qdrant]
    embeddings = embedder.embed_chunks(texts_to_embed)

    # 3. Store in Qdrant
    qdrant_db = QdrantManager(db_path=db_path)

    qdrant_db.setup_collection(
        collection_name=collection_name,
        vector_size=embedder.vector_size
    )

    qdrant_db.insert_chunks(
        collection_name=collection_name,
        chunks=chunks_for_qdrant,
        embeddings=embeddings
    )

    print("\n[+] Process complete! Document embeddings are now stored in Qdrant.")
