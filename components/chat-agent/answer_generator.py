from local_llm import LocalInferenceClient

class AnswerGenerator:
    def __init__(self, model_path: str = None):
        """
        Initializes a local, CPU-based GGUF model via llama-cpp-python (no API/billing needed).
        """
        self.client = LocalInferenceClient(model_path) if model_path else LocalInferenceClient()

    def generate_answer(self, query: str, contexts: list, history: list = None) -> str:
        """
        Formats the retrieved context and sends it to the cloud model for generation.
        `history` (optional) is a list of prior {"role", "content"} turns for continuity.
        """
        # Format the retrieved chunks into a single readable context block
        context_text = "\n\n".join([f"Page {c['page_number']}: {c['text']}" for c in contexts])

        # Build the ChatML-style messages payload
        messages = [
            {"role": "system", "content": "You are a precise assistant. Answer the user's question strictly based on the provided context."},
            *(history or []),
            {"role": "user", "content": f"Context:\n{context_text}\n\nQuestion: {query}"}
        ]
        
        try:
            response = self.client.chat_completion(
                messages=messages,
                max_tokens=512,
                temperature=0.3
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"Error generating answer locally: {e}"