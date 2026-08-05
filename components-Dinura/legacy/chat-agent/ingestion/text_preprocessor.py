import os
import re
import unicodedata


class TextPreprocessor:
    """
    Cleans page-wise PDF text and prepares it for
    chunk generation and embedding.
    """

    def preprocess(self, pages, pdf_path):
        
        # document_name and document_id are removed here 
        # since they are excluded from your final flat JSON output

        cleaned_pages = []

        for page in pages:

            text = page["text"]

            # --------------------------------------------------
            # Unicode normalization
            # --------------------------------------------------
            text = unicodedata.normalize("NFKC", text)

            # --------------------------------------------------
            # Normalize symbols
            # --------------------------------------------------
            replacements = {
                "“": '"',
                "”": '"',
                "‘": "'",
                "’": "'",
                "–": "-",
                "—": "-",
                "•": "-",
                "": "-",
                "✓": "-",
                "✔": "-",
                "\u00A0": " "
            }

            for old, new in replacements.items():
                text = text.replace(old, new)

            # --------------------------------------------------
            # Remove repeated headers
            # --------------------------------------------------
            text = re.sub(r"EDABS.*", "", text, flags=re.IGNORECASE)
            text = re.sub(r"Lecturer:.*", "", text, flags=re.IGNORECASE)

            # --------------------------------------------------
            # Remove standalone page numbers
            # --------------------------------------------------
            text = re.sub(
                r"^\s*\d+\s*$",
                "",
                text,
                flags=re.MULTILINE
            )

            # --------------------------------------------------
            # Merge wrapped hyphenated words 
            # (e.g., "off\n- shore" -> "offshore")
            # --------------------------------------------------
            text = re.sub(r"([a-zA-Z]+)\s*\n\s*-\s*([a-zA-Z]+)", r"\1\2", text)

            # --------------------------------------------------
            # Remove bullet dashes (dashes at the beginning of a line)
            # --------------------------------------------------
            text = re.sub(r"(?:^|\n)\s*-\s*", " ", text)

            # --------------------------------------------------
            # Flatten the text (replace all newlines with spaces)
            # --------------------------------------------------
            text = text.replace("\n", " ")

            # --------------------------------------------------
            # Remove any resulting multiple spaces
            # --------------------------------------------------
            text = re.sub(r"[ \t]+", " ", text)

            # --------------------------------------------------
            # Append only the strictly requested fields
            # --------------------------------------------------
            cleaned_pages.append(
                {
                    "page_index": page["page_number"] - 1,
                    "page_number": page["page_number"],
                    "page_content": text.strip()
                }
            )

        return cleaned_pages