from types import SimpleNamespace
from llama_cpp import Llama

DEFAULT_MODEL_PATH = "models/qwen2.5-3b-instruct-q4_k_m.gguf"


class LocalInferenceClient:
    """
    Drop-in replacement for huggingface_hub.InferenceClient's `.chat_completion()`,
    backed by a local GGUF model via llama-cpp-python (CPU-only, no API/billing needed).

    Each distinct (model_path, n_ctx) is loaded once and shared across all instances that
    ask for it. Keying on the path matters: the evaluator agent runs a different model
    family than the generator on purpose, so a single shared slot would silently hand the
    judge whichever model happened to load first.
    """

    _models = {}

    def __init__(self, model_path: str = DEFAULT_MODEL_PATH, n_ctx: int = 4096):
        key = (model_path, n_ctx)
        if key not in LocalInferenceClient._models:
            print(f"[*] Loading local model: {model_path} (first load only)...")
            LocalInferenceClient._models[key] = Llama(
                model_path=model_path,
                n_ctx=n_ctx,
                n_threads=None,  # let llama.cpp auto-detect CPU cores
                verbose=False,
            )
        self.model_path = model_path
        self.model = LocalInferenceClient._models[key]

    def chat_completion(self, messages, max_tokens=512, temperature=0.3, schema=None):
        """
        Passing `schema` compiles it into a llama.cpp grammar, so the reply is forced to be
        JSON matching that shape. Generators that must return structured data use it; the
        chat path leaves it None and gets ordinary prose.
        """
        kwargs = {
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if schema is not None:
            kwargs["response_format"] = {"type": "json_object", "schema": schema}

        result = self.model.create_chat_completion(**kwargs)
        content = result["choices"][0]["message"]["content"]
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])
