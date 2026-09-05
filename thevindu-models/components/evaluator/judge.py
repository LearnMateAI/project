"""
Same job as components-Dinura/learnmate/evaluator/judge.py.

Pass `llm=` to grade with a candidate GGUF without touching LEARNMATE_JUDGE_MODEL.
"""

from learnmate.evaluator.judge import Judge, get_judge
from learnmate.llm.llamacpp import LlamaCppChatModel


def judge_with_gguf(gguf_path, n_ctx=8192, threshold=70):
    """Build the live Judge around a comparison GGUF."""
    llm = LlamaCppChatModel(
        gguf_path=str(gguf_path),
        n_ctx=n_ctx,
        chat_format=None,
        temperature=0.0,
        max_tokens=512,
    )
    return Judge(llm=llm, threshold=threshold)


__all__ = ["Judge", "get_judge", "judge_with_gguf"]
