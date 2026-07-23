# format the full document into its heading, subheading hierachy if any.
# otherwise form the text in to topic - description pairs.
# The idea is to retain the context.

import re

class TextPreprocessor:
    """
    Formats the full document into its heading and subheading hierarchy.
    Chunks the text into topic-description structures to retain context.
    """

    def __init__(self):
        # Matches "CHAPTER - I", "CHAPTER - II", etc.
        self.chapter_pattern = r"(?i)^CHAPTER\s*-\s*[IVXLCDM]+\b"

    def process(self, text: str) -> list:
        """
        Processes text into hierarchical chunks.

        Args:
            text (str): Cleaned text.

        Returns:
            list: A list of dictionaries containing 'heading' and 'content'.
        """
        chunks = []
        lines = text.split('\n')
        
        current_heading = "Front Matter / Introduction"
        current_content = []

        for line in lines:
            # Check if the line is a Chapter heading
            if re.match(self.chapter_pattern, line.strip()):
                # Save the accumulated content under the previous heading
                if current_content:
                    chunks.append({
                        "heading": current_heading,
                        "content": "\n".join(current_content).strip()
                    })
                # Start a new chunk
                current_heading = line.strip()
                current_content = []
            else:
                current_content.append(line)

        # Append the final chunk
        if current_content:
            chunks.append({
                "heading": current_heading,
                "content": "\n".join(current_content).strip()
            })

        return chunks