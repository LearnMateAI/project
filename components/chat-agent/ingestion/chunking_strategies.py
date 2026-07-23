from abc import ABC, abstractmethod
from typing import List
from ingestion.document_models import Page, Chunk

class BaseChunker(ABC):
    @abstractmethod
    def chunk(self, pages: List[Page], doc_metadata: dict) -> List[Chunk]:
        pass

class SlideChunker(BaseChunker):
    """
    Best for Lecture PDFs / Presentations.
    Strategy: 1 Slide = 1 Vector Chunk.
    """
    def chunk(self, pages: List[Page], doc_metadata: dict) -> List[Chunk]:
        chunks = []
        for page in pages:
            # Skip empty or very short slides
            if len(page.text) < 20: 
                continue
                
            meta = doc_metadata.copy()
            meta.update({
                "page_number": page.page_number,
                "chunk_type": "slide"
            })
            
            chunks.append(Chunk(content=page.text, metadata=meta))
        return chunks

class TopicChunker(BaseChunker):
    """
    Best for Textbooks, Articles, and General Long-form Documents.
    Strategy: Chunking by small topic / paragraph to retain tight context.
    """
    def __init__(self, max_chunk_size: int = 1000):
        self.max_chunk_size = max_chunk_size

    def chunk(self, pages: List[Page], doc_metadata: dict) -> List[Chunk]:
        chunks = []
        
        # We process page by page to respect page boundaries, but combine small paragraphs
        current_chunk_text = ""
        primary_page = 1
        
        for page in pages:
            # Split the page text by double newlines which we preserved as paragraph boundaries
            paragraphs = page.text.split('\n\n')
            
            for para in paragraphs:
                para = para.strip()
                if not para:
                    continue
                
                # If adding this paragraph exceeds chunk size, save the current chunk first
                if current_chunk_text and len(current_chunk_text) + len(para) > self.max_chunk_size:
                    meta = doc_metadata.copy()
                    meta.update({
                        "page_number": primary_page,
                        "chunk_type": "topic_based"
                    })
                    chunks.append(Chunk(content=current_chunk_text.strip(), metadata=meta))
                    current_chunk_text = ""
                
                # If it's a fresh chunk, record the starting page
                if not current_chunk_text:
                    primary_page = page.page_number
                    
                # Append paragraph
                if current_chunk_text:
                    current_chunk_text += "\n\n" + para
                else:
                    current_chunk_text = para
                    
        # Add the final chunk if any remains
        if current_chunk_text:
            meta = doc_metadata.copy()
            meta.update({
                "page_number": primary_page,
                "chunk_type": "topic_based"
            })
            chunks.append(Chunk(content=current_chunk_text.strip(), metadata=meta))
            
        return chunks