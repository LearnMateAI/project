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

    # A locally-built model -- the merged finetune from scripts/build_finetuned_gguf.py --
    # exists in no Hugging Face repo, so there is nothing to fall back to and the honest
    # answer is to say which file is missing and how it is made. Configured by leaving
    # LEARNMATE_GENERATOR_REPO empty.
    if not repo_id or not filename:
        raise FileNotFoundError(
            f"{target} does not exist, and no download source is configured for it. "
            f"If this is the finetuned model, build it with:\n"
            f"    python scripts/build_finetuned_gguf.py\n"
            f"Otherwise set the matching *_REPO and *_FILE, or point the model setting at "
            f"a GGUF that exists."
        )

    # The downloaded file keeps its name from the repo, so a filename that disagrees with
    # the configured path silently yields a *different model than the one asked for* --
    # the base model answering where a finetune was configured, which reads as the
    # finetune being disappointing rather than as a misconfiguration.
    if filename != target.name:
        print(f"[!] {target.name} is missing and the configured download is {filename!r}, "
              f"which is a different file. Loading {filename!r} instead -- if you meant to "
              f"run {target.name}, this is NOT it.")

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
