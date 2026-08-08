import io
import pdfplumber

def extract_text_from_pdf(file_bytes: bytes) -> list[str]:
    """
    Extracts plain text from each page of a PDF.
    Returns one string per page, in page order (index 0 = page 1).
    """
    pages=[]
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            pages.append(text)
    return pages