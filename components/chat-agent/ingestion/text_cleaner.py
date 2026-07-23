# Cleaning page numbers, headers, footers, spaces in between.abs

import re

class TextCleaner:
    """
    Cleans extracted PDF text by removing page numbers, excessive whitespaces, 
    and fixing broken hyphenated words.
    """

    @staticmethod
    def clean(text: str) -> str:
        if not text:
            return ""
            
        # Remove null characters
        text = text.replace('\x00', '')
        
        # Fix hyphenated words at the end of lines
        text = re.sub(r'-\n', '', text)
        
        # We want to reconstruct paragraphs. 
        # A simple heuristic: if a line is short or ends with a punctuation mark, 
        # or the next line starts with a capital, it might be a boundary.
        # But strictly simple: just preserve double newlines if they exist, 
        # and join single newlines with a space.
        
        text = text.replace('\n\n', ' <PARAGRAPH_BREAK> ')
        text = text.replace('\n', ' ')
        
        # Clean up excessive spaces
        text = re.sub(r'\s+', ' ', text)
        
        # Restore paragraph breaks
        cleaned_text = text.replace('<PARAGRAPH_BREAK>', '\n\n')
        
        return cleaned_text.strip()