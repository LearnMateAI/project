import os
from google import genai
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL")  # set to whatever model string worked in your Phase 0 practice

client = genai.Client(api_key=GEMINI_API_KEY)


def generate_summary(document_text: str) -> str:
    """
    Generates a plain-language summary of a document's content using Gemini.

    Simplified version of FR-13/FR-11: the SRS specifies routing this
    generation request to a fine-tuned Qwen 2.5 model first, falling back to
    Gemini only if that endpoint is unavailable. This MVP calls Gemini
    directly — the fine-tuned model and routing logic are Iteration 2 work.
    """
    prompt = (
        "You are a study assistant helping a law student review their own "
        "lecture notes. Based only on the document text below, write a clear, "
        "well-organized summary in plain English, covering the main topics "
        "and arguments. Do not add legal advice or information not present "
        "in the text.\n\n"
        f"DOCUMENT TEXT:\n{document_text}"
    )

    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
    )
    return response.text.strip()