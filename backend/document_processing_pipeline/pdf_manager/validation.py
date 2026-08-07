import io 
import pdfplumber

"targeted at 50 MB / 300 pages per document for the pilot"
MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB
MAX_PAGE_COUNT = 300  # 300 pages
ALLOWED_FILE_TYPES = ["application/pdf"]

def validate_pdf(file_bytes: bytes, content_type: str, file_name: str) -> int:
    """
    Validates an uploaded file against SRS FR-5 / UI-03 / FR-6 rules.
    Returns the page count on success. Raises ValueError with a
    human-readable message on failure (SRS DOC-04).
    """
    if not file_name.lower().endswith(".pdf"):
        raise ValueError("Only PDF files are allowed.")
    if len(file_bytes) > MAX_FILE_SIZE_BYTES:
        raise ValueError(f"File size exceeds the maximum allowed size of {MAX_FILE_SIZE_BYTES / (1024 * 1024)} MB.")
    try:
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            page_count = len(pdf.pages)
    except Exception:
        # Covers corrupted files and password-protected PDFs (FR-6)
        raise ValueError(
            "This PDF could not be read. It may be corrupted or password-protected — "
            "please upload an unprotected copy."
        )

    if page_count == 0:
        raise ValueError("This PDF appears to have no pages.")
    if page_count > MAX_PAGE_COUNT:
        raise ValueError(f"Page count exceeds the maximum allowed count of {MAX_PAGE_COUNT} pages.")

    return page_count