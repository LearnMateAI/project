import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(__file__)))  # chat-agent/ for local_llm
from local_llm import LocalInferenceClient


class QueryRewriter:
    """Turns a follow-up question into a standalone one, using chat history, so retrieval still works."""

    def __init__(self, model_path: str = None):
        self.client = LocalInferenceClient(model_path) if model_path else LocalInferenceClient()

    def rewrite(self, history: list[dict], query: str) -> str:
        if not history:
            return query

        history_text = "\n".join(f"{m['role']}: {m['content']}" for m in history)
        messages = [
            {"role": "system", "content": (
                "Rewrite the follow-up question into a standalone question, resolving any "
                "pronouns or references using the conversation history. Output only the "
                "rewritten question, nothing else."
            )},
            {"role": "user", "content": f"Conversation history:\n{history_text}\n\nFollow-up question: {query}"}
        ]

        try:
            response = self.client.chat_completion(messages=messages, max_tokens=100, temperature=0.0)
            rewritten = response.choices[0].message.content.strip()
            return rewritten or query
        except Exception:
            return query  # fall back to the raw query if rewriting fails
