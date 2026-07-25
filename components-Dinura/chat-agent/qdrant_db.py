from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
import uuid

class QdrantManager:
    def __init__(self, db_path: str = "./qdrant_data"):
        """
        Initializes a local persistent Qdrant client.
        Data will be saved in the specified folder.
        """
        print(f"[*] Connecting to Qdrant at {db_path}...")
        self.client = QdrantClient(path=db_path)

    def setup_collection(self, collection_name: str, vector_size: int):
        """Creates the collection if it does not already exist."""
        if not self.client.collection_exists(collection_name):
            print(f"[*] Creating new collection: '{collection_name}' (Size: {vector_size})")
            self.client.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
            )
        else:
            print(f"[*] Collection '{collection_name}' already exists.")

    def insert_chunks(self, collection_name: str, chunks: list, embeddings: list):
        """
        Pairs chunks with their embeddings and uploads them to Qdrant.
        """
        print(f"[*] Uploading {len(chunks)} vectors to Qdrant...")
        
        points = []
        for chunk, embedding in zip(chunks, embeddings):
            # We store the raw text and original metadata in the payload
            payload = {
                "text": chunk.content,
                **chunk.metadata
            }
            
            points.append(
                PointStruct(
                    id=str(uuid.uuid4()), # Generate a unique ID for each vector
                    vector=embedding.tolist(),
                    payload=payload
                )
            )

        # Upsert the points into Qdrant
        self.client.upsert(
            collection_name=collection_name,
            points=points
        )
        print("[+] Upload complete.")