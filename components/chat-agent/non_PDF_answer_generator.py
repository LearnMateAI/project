from local_llm import LocalInferenceClient

class GeneralAnswerGenerator:
    def __init__(self, model_path: str = None):
        """
        Initializes a local, CPU-based GGUF model for general knowledge queries.
        """
        self.client = LocalInferenceClient(model_path) if model_path else LocalInferenceClient()

    def generate_answer(self, query: str, history: list = None) -> str:
        """
        Sends the query directly to the LLM without PDF context.
        `history` (optional) is a list of prior {"role", "content"} turns for continuity.
        """
        messages = [
            {"role": "system", "content": "You are a helpful, knowledgeable AI assistant. Answer the user's question accurately based on your general knowledge."},
            *(history or []),
            {"role": "user", "content": query}
        ]
        
        try:
            response = self.client.chat_completion(
                messages=messages,
                max_tokens=512,
                temperature=0.6  # Slightly higher temperature for general knowledge
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"Error generating answer locally: {e}"