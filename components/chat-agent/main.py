import os
from ingestion.pdf_loader import PDFLoader
from ingestion.chunking_strategies import SlideChunker, TopicChunker

def main():
    print("=" * 50)
    print("Multi-Type Document Ingestion Pipeline")
    print("=" * 50)

    pdf_path = input("Enter PDF path: ").strip()
    
    print("\nSelect Document Type:")
    print("1. Lecture Slides / Presentation (1 chunk per page)")
    print("2. Textbook / General Document (Topic-based paragraph chunking)")
    doc_type = input("Enter choice (1 or 2): ").strip()

    try:
        loader = PDFLoader(pdf_path)
        pages = loader.load()
        print(f"\n[+] PDF loaded successfully. ({len(pages)} pages)")

        # Extract base metadata (e.g., filename without extension)
        doc_name = os.path.basename(pdf_path)
        base_metadata = {"source": doc_name}

        # Select Strategy
        if doc_type == "1":
            chunker = SlideChunker()
        else:
            # Use small topic-based chunks based on natural paragraphs
            chunker = TopicChunker(max_chunk_size=1000)

        # Process Document
        structured_chunks = chunker.chunk(pages, base_metadata)
        
        print(f"[+] Text preprocessed into {len(structured_chunks)} logical chunks ready for VectorDB.")

        # Display sample of the parsed chunks
        print("\n----- Sample Extracted Chunks -----")
        for i, chunk in enumerate(structured_chunks[:3]):
            print(f"\n>>> CHUNK {i+1} | METADATA: {chunk.metadata}")
            content_preview = chunk.content[:200].replace('\n', ' ')
            print(f"    CONTENT: {content_preview}...")

    except Exception as e:
        print(f"\nError: {e}")

if __name__ == "__main__":
    main()