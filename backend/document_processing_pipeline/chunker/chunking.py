def chunk_document(pages: list[str], chunk_size: int = 1000, overlap: int = 150) -> list[dict]:
    """
    Splits each page's cleaned text into fixed-size, overlapping character
    windows, tagged with the page they came from.
    The overlap exists so that a sentence sitting right at a chunk boundary
    still appears in full inside at least one chunk, rather than being cut
    in half and lost from both.
    """
    chunks = []
    chunk_index = 0
    step = chunk_size - overlap

    for page_number, page_text in enumerate(pages, start=1):
        text = page_text.strip()
        if not text:
            continue
        for start in range(0,len(text), step):
            piece = text[start:start + chunk_size].strip()
            if piece:
                chunks.append({
                    "chunk_index": chunk_index,
                    "page_number": page_number,
                    "text": piece
                })
                chunk_index += 1
            if start + chunk_size >= len(text):
                break
    return chunks