from embedding_generator import EmbeddingGenerator
from qdrant_client import QdrantClient

class DocumentRetriever:
    def __init__(self, db_path: str = "./qdrant_data", collection_name: str = "knowledge_base"):
        self.client = QdrantClient(path=db_path)
        self.collection_name = collection_name
        self.embedder = EmbeddingGenerator()

    def retrieve(self, query: str, top_k: int = 3) -> list[dict]:
        """
        Embeds the search query and retrieves the top_k closest chunks from Qdrant.
        """
        # Convert user query string into vector
        query_vector = self.embedder.embed_chunks([query])[0]

        # Search Qdrant collection using the new query_points API
        response = self.client.query_points(
            collection_name=self.collection_name,
            query=query_vector.tolist(),
            limit=top_k
        )

        results = []
        # .points contains the actual list of matched records
        for hit in response.points:
            results.append({
                "score": hit.score,
                "text": hit.payload.get("text", ""),
                "page_number": hit.payload.get("page_number", "N/A"),
                "source": hit.payload.get("source", "N/A")
            })

        return results