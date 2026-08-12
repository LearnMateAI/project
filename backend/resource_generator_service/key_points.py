import os
import json
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL")

client = genai.Client(api_key=GEMINI_API_KEY)


def generate_key_points(document_text: str) -> list[str]:
    """
    Generates a list of key points from a document using Gemini, requesting
    structured JSON output so the result is directly usable as a list
    rather than free-form text needing fragile manual parsing.
    """
    prompt = (
        "You are a study assistant helping a law student review their own "
        "lecture notes. Based only on the document text below, extract the "
        "8 to 12 most important key points a student should remember. "
        "Return ONLY a JSON array of strings, one per key point, with no "
        "other text.\n\n"
        f"DOCUMENT TEXT:\n{document_text}"
    )

    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(response_mime_type="application/json"),
    )

    try:
        points = json.loads(response.text)
        if isinstance(points, list):
            return [str(p).strip() for p in points if str(p).strip()]
    except (json.JSONDecodeError, TypeError):
        pass

    return [line.strip("-• \t") for line in response.text.split("\n") if line.strip()]