from embedding_generator import EmbeddingGenerator
from qdrant_db import QdrantManager

class DocumentChunk:
    """A simple wrapper to format data for Qdrant storage."""
    def __init__(self, content, metadata):
        self.content = content
        self.metadata = metadata

def process_and_store_embeddings(formatted_data: list, pdf_path: str, collection_name: str = "knowledge_base"):
    """
    Takes formatted dictionary data, generates embeddings, and stores them in Qdrant.
    """
    print("\n--- Starting Vectorization & Storage ---")
    
    # 1. Convert dictionaries into the object structure QdrantManager expects
    chunks_for_qdrant = [
        DocumentChunk(
            content=item["page_content"], 
            metadata={
                "page_index": item["page_index"], 
                "page_number": item["page_number"],
                "source": pdf_path
            }
        )
        for item in formatted_data
    ]

    # 2. Generate Embeddings
    embedder = EmbeddingGenerator()
    texts_to_embed = [chunk.content for chunk in chunks_for_qdrant]
    embeddings = embedder.embed_chunks(texts_to_embed)

    # 3. Store in Qdrant
    qdrant_db = QdrantManager()
    
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