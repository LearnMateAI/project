"""
Getting a GGUF file onto disk.

Only the llama.cpp backend needs this, and only the first time: the two models this
project uses are ~2 GB each, too large to keep in git, so a missing one is fetched from
Hugging Face rather than being an error the user has to go and fix by hand.
"""

from pathlib import Path

from .. import config


def ensure_gguf(path: str, repo_id: str, filename: str) -> str:
    """
    Return a local path to a GGUF file, downloading it on first use.

    A finetuned model supplied as a plain file is used as-is; the download only happens
    when the configured path does not exist and a repo is known. That ordering is what
    lets someone drop their own GGUF at the configured path and have it picked up without
    touching any config.
    """
    target = Path(path)
    if target.exists():
        return str(target)

    from huggingface_hub import hf_hub_download  # lazy: not needed once models are local

    models_dir = target.parent if target.parent.name else config.MODELS_DIR
    models_dir.mkdir(parents=True, exist_ok=True)
    print(f"[*] {target.name} not found locally; downloading from {repo_id} (~2 GB, once)...")

    # HF_TOKEN only lifts anonymous rate limits here; both default models are public.
    return hf_hub_download(
        repo_id=repo_id,
        filename=filename,
        local_dir=str(models_dir),
        token=config.HF_TOKEN,
    )
