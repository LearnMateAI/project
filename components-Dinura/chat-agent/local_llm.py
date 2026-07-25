from types import SimpleNamespace
from llama_cpp import Llama

DEFAULT_MODEL_PATH = "models/qwen2.5-3b-instruct-q4_k_m.gguf"


class LocalInferenceClient:
    """
    Drop-in replacement for huggingface_hub.InferenceClient's `.chat_completion()`,
    backed by a local GGUF model via llama-cpp-python (CPU-only, no API/billing needed).
    The model is loaded once and shared across all instances.
    """

    _model = None

    def __init__(self, model_path: str = DEFAULT_MODEL_PATH, n_ctx: int = 4096):
        if LocalInferenceClient._model is None:
            print(f"[*] Loading local model: {model_path} (first load only)...")
            LocalInferenceClient._model = Llama(
                model_path=model_path,
                n_ctx=n_ctx,
                n_threads=None,  # let llama.cpp auto-detect CPU cores
                verbose=False,
            )
        self.model = LocalInferenceClient._model

    def chat_completion(self, messages, max_tokens=512, temperature=0.3):
        result = self.model.create_chat_completion(
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        content = result["choices"][0]["message"]["content"]
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])
