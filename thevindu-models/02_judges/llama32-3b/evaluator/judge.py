"""
Same job as components-Dinura/learnmate/evaluator/judge.py.

Builds the live Judge around `Llama-3.2-3B-Instruct-Q4_K_M.gguf` without changing `.env`.
"""

MODEL_ID = 'llama32-3b'
GGUF = 'Llama-3.2-3B-Instruct-Q4_K_M.gguf'
PAIR_GENERATOR = 'qwen25-3b'

from pathlib import Path

from learnmate.evaluator.judge import Judge
from learnmate.llm.llamacpp import LlamaCppChatModel
from learnmate import config


def get_candidate_judge(threshold: int = 70) -> Judge:
    path = Path(config.MODELS_DIR) / GGUF
    llm = LlamaCppChatModel(
        gguf_path=str(path),
        n_ctx=8192,
        chat_format=None,
        temperature=0.0,
        max_tokens=512,
    )
    return Judge(llm=llm, threshold=threshold)
