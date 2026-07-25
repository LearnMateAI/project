"""
pdf_loader.py

Loads a PDF file and extracts text page by page.
"""

import fitz  # PyMuPDF


def extract_pdf_text(pdf_path: str):
    """
    Extract text from a PDF page by page.
    """

    pages = []

    try:
        document = fitz.open(pdf_path)

        for page_num in range(len(document)):
            page = document.load_page(page_num)
            text = page.get_text("text")

            pages.append({
                "page_number": page_num + 1,
                "text": text.strip()
            })

        document.close()

    except Exception as e:
        print(f"Error loading PDF: {e}")
        return []

    return pages