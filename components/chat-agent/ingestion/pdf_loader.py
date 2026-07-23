from pathlib import Path
from pypdf import PdfReader
from ingestion.document_models import Page
from ingestion.text_cleaner import TextCleaner

class PDFLoader:
    """Loads a PDF and extracts text while preserving page numbers."""

    def __init__(self, pdf_path: str):
        self.pdf_path = Path(pdf_path)

    def load(self) -> list[Page]:
        if not self.pdf_path.exists():
            raise FileNotFoundError(f"PDF not found: {self.pdf_path}")

        reader = PdfReader(str(self.pdf_path))
        pages = []

        for i, page in enumerate(reader.pages):
            text = page.extract_text()
            if text:
                # Clean text to remove artifacts and extra whitespace
                clean_text = TextCleaner.clean(text)
                if clean_text:
                    pages.append(Page(page_number=i + 1, text=clean_text))

        return pages