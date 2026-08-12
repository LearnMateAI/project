import re

def clean_pages(pages: list[str]) -> list[str]:
    """
    Light per-page cleaning: strips lines that are just a page number, and
    collapses excess whitespace.
    """
    cleaned = []
    for page_text in pages:
        lines = page_text.split("\n")
        kept_lines = [
            line.strip() for line in lines
            if line.strip() and not re.fullmatch(r"[-\s]*\d{1,4}[-\s]*", line.strip())
        ]
        cleaned_text = " ".join(kept_lines)
        cleaned_text = re.sub(r"\s{2,}", " ", cleaned_text)
        cleaned.append(cleaned_text.strip())
    return cleaned