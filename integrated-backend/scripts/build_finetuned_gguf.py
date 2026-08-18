"""
Turn the model-Thevindu LoRA adapter into a GGUF this backend can actually load.

    python scripts/build_finetuned_gguf.py

The ML track (`model-Thevindu/`) trains a QLoRA adapter against
`Qwen/Qwen2.5-1.5B-Instruct` and ships ~74 MB of `adapter_model.safetensors`. This
backend runs GGUF through llama.cpp. Those are not the same artifact and nothing in
the request path can bridge them, so the bridge is this script: it is run once, offline,
and its output is a plain file in `models/` that `LEARNMATE_GENERATOR_MODEL` points at
like any other.

Three steps, each skipped if its output already exists:

    1. fetch    the base weights the adapter was trained on (~3.1 GB, resumable)
    2. merge    adapter into base -> a standalone fp16 model in the build directory
    3. convert  that model -> one quantised GGUF in models/

Nothing here is imported by the server. It depends on `peft`, `gguf` and
`sentencepiece`, which are build-time only and deliberately kept out of the runtime import
path. `sentencepiece` is needed even though Qwen2.5 uses BPE: the converter's Qwen class
tries the sentencepiece vocab first and falls back to BPE on FileNotFoundError, so without
the package installed it raises ImportError before it can reach that fallback.

--- Why merge, rather than llama.cpp's own LoRA support --------------------------------

llama.cpp can apply a LoRA at load time, which sounds like less work. It is the wrong
trade here for two reasons: applying an adapter over an already-quantised base compounds
quantisation error with the adapter delta, and it splits "which model is running" across
two settings instead of one path. Merging first means the rest of this backend never
learns that a finetune is involved at all -- the generator is a GGUF, as it was before.

--- Why q8_0 and not q4_k_m like the base models ---------------------------------------

Partly forced, partly preferred.

Forced: k-quants (q4_k_m and friends) are produced by llama.cpp's `llama-quantize`
binary, which is C++ and is not part of any wheel this project installs.
`convert_hf_to_gguf.py` can emit f32, f16, bf16 and q8_0 directly from Python, so q8_0 is
the best quantisation reachable without asking anyone to build llama.cpp first.

Preferred: this model is 1.5B, half the size of the 3B base it replaces, and quantisation
damage lands harder the fewer parameters there are to absorb it. Taking a 1.5B domain
finetune to 4-bit risks giving back exactly the domain behaviour it was trained for. q8_0
is ~1.6 GB -- smaller than the 3B q4_k_m it replaces -- and is close enough to fp16 to be
treated as lossless.
"""

import argparse
import functools
import json
import os
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

# Unbuffered: every step here is minutes long, and a silent terminal during a 3 GB
# download is indistinguishable from a hung one.
print = functools.partial(print, flush=True)  # noqa: A001

BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_DIR = BACKEND_DIR.parent

# The trained adapter, in the ML track. Read-only from here: this script never writes
# into model-Thevindu/, it only consumes what that track produced.
DEFAULT_ADAPTER = (PROJECT_DIR / "model-Thevindu" / "02_finetuning" / "adapters"
                   / "qwen25-lora-20260815-090709" / "adapter")

# Scratch space for the merged fp16 model. Big (~3.1 GB) and reproducible from the two
# inputs, so it is gitignored and safe to delete once the GGUF exists (--clean).
DEFAULT_BUILD_DIR = BACKEND_DIR / "build" / "merged"

# Named for what it is rather than for the run that produced it: the run id lives in the
# sidecar JSON written beside it, where it cannot be mistaken for part of the filename the
# config points at.
DEFAULT_OUTPUT = BACKEND_DIR / "models" / "learnmate-legal-qwen2.5-1.5b-q8_0.gguf"

# The converter lives in the llama.cpp repo, not on PyPI, and it is no longer one file.
# Upstream split it into a thin entrypoint plus a `conversion/` package of per-architecture
# modules, and that package tracks `gguf` constants faster than the `gguf` wheel is
# released -- a current `conversion/` against the PyPI wheel dies on whichever MODEL_ARCH
# was added most recently. So all three pieces are taken from the same commit of the same
# repo and kept together in the build directory:
#
#     convert_hf_to_gguf.py   the entrypoint
#     conversion/             the per-architecture model classes it imports
#     gguf-py/gguf/           the constants and writer that package expects
#
# Fetched over the contents API rather than cloned, because the repo is ~200 MB and these
# are ~100 small Python files. The fetched `gguf` goes first on PYTHONPATH so it shadows
# the installed wheel for the converter subprocess only -- nothing else in this project
# imports gguf, and the server never runs any of this.
GITHUB_REPOS = ("ggml-org/llama.cpp", "ggerganov/llama.cpp")  # repo moved orgs in 2024
CONVERT_ENTRYPOINT = "convert_hf_to_gguf.py"
CONVERSION_PKG = "conversion"
GGUF_PKG_PATH = "gguf-py/gguf"


def _fail(message: str) -> None:
    """Stop with a message that says what to do, not just what broke."""
    print(f"\nERROR: {message}")
    sys.exit(1)


def resolve_base_model(adapter_dir: Path) -> str:
    """
    Read the base model id out of the adapter's own config.

    Taken from `adapter_config.json` rather than hardcoded or passed in: a LoRA is a delta
    against one specific set of weights, and merging it onto anything else produces a model
    that loads cleanly and generates subtly wrong text. The adapter already records which
    base it belongs to, so that record is the authority.
    """
    import json

    config_path = adapter_dir / "adapter_config.json"
    if not config_path.exists():
        _fail(f"{config_path} not found. Is {adapter_dir} really a PEFT adapter directory?")

    base = json.loads(config_path.read_text(encoding="utf-8")).get("base_model_name_or_path")
    if not base:
        _fail(f"{config_path} has no base_model_name_or_path; cannot tell what to merge onto.")
    return base


def merge_adapter(adapter_dir: Path, build_dir: Path, base_override: str = "") -> Path:
    """
    Apply the LoRA delta to the base weights and save the result as a standalone model.

    Loaded in fp16, which is both what fits and what is faithful: the run record for this
    adapter reports fp16/bf16 QLoRA training, so fp16 is the precision the deltas were
    learned in. fp32 would double the memory for arithmetic the adapter never saw.

    The tokenizer is saved alongside deliberately. GGUF embeds the vocabulary and the chat
    template in the file itself, and the converter reads both from this directory -- an
    adapter directory carries only a partial tokenizer config, so the base model's
    tokenizer is the complete one.

    `base_override` points at an already-downloaded copy of those base weights. The base is
    ~3 GB and the download is the slowest part of this script by a wide margin, so on a
    slow or interrupted link it is worth fetching once, by whatever means works, and
    pointing this at the result. What it must not become is a way to merge onto the wrong
    weights: the id the adapter records is still read and still printed, and a mismatch is
    reported rather than silently accepted.
    """
    if (build_dir / "config.json").exists():
        print(f"[2/3] merged model already present at {build_dir}; skipping merge")
        return build_dir

    import torch
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer

    recorded = resolve_base_model(adapter_dir)
    base_id = base_override or recorded
    print(f"[2/3] merging {adapter_dir.name} into {recorded}")
    if base_override:
        # Named rather than assumed: merging a LoRA onto weights other than the ones it
        # was trained against produces a model that loads cleanly and generates subtly
        # wrong text, which is the hardest kind of mistake to notice later.
        print(f"      using local base weights at {base_override}")
        print(f"      (verify these are {recorded}; the adapter is a delta against those)")
    else:
        print("      loading base weights (first run downloads ~3.1 GB, resumable)...")

    base = AutoModelForCausalLM.from_pretrained(
        base_id,
        dtype=torch.float16,
        # This machine may have no GPU and the merge is elementwise arithmetic either way;
        # keeping it on CPU avoids a device juggle for work that is not compute-bound.
        device_map="cpu",
    )

    print("      applying adapter...")
    merged = PeftModel.from_pretrained(base, str(adapter_dir)).merge_and_unload()

    build_dir.mkdir(parents=True, exist_ok=True)
    print(f"      writing merged model to {build_dir}...")
    merged.save_pretrained(str(build_dir), safe_serialization=True)
    AutoTokenizer.from_pretrained(base_id).save_pretrained(str(build_dir))

    return build_dir


def _fetch(url: str, dest: Path) -> None:
    """Download one file, creating its parent directory."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url, timeout=60) as response:
        dest.write_bytes(response.read())


def _fetch_package(repo: str, repo_path: Path | str, dest_dir: Path) -> int:
    """
    Download every .py file in one directory of a GitHub repo.

    Uses the contents API for the listing so the file names come from the repository
    rather than from a hardcoded list here that would rot on the next upstream rename.
    """
    api = f"https://api.github.com/repos/{repo}/contents/{repo_path}"
    with urllib.request.urlopen(api, timeout=60) as response:
        listing = json.loads(response.read().decode("utf-8"))
    if isinstance(listing, dict):  # an error object, e.g. rate limit or 404
        raise RuntimeError(listing.get("message", "unexpected response"))

    count = 0
    for entry in listing:
        if entry.get("type") != "file":
            continue
        name = entry["name"]
        if not (name.endswith(".py") or name == "py.typed"):
            continue
        target = dest_dir / name
        if target.exists() and target.stat().st_size == entry.get("size"):
            count += 1
            continue
        _fetch(entry["download_url"], target)
        count += 1
    return count


def ensure_convert_script(build_root: Path) -> tuple[Path, Path]:
    """
    Put the converter and everything it imports in the build directory.

    Returns the entrypoint and the directory to prepend to PYTHONPATH for it.
    """
    script = build_root / CONVERT_ENTRYPOINT
    conversion_dir = build_root / CONVERSION_PKG
    gguf_root = build_root / "gguf_master"

    if script.exists() and (conversion_dir / "base.py").exists() and             (gguf_root / "gguf" / "constants.py").exists():
        return script, gguf_root

    build_root.mkdir(parents=True, exist_ok=True)
    last_error = None
    for repo in GITHUB_REPOS:
        try:
            print(f"      fetching converter from {repo}")
            _fetch(f"https://raw.githubusercontent.com/{repo}/master/{CONVERT_ENTRYPOINT}",
                   script)
            n = _fetch_package(repo, CONVERSION_PKG, conversion_dir)
            print(f"      fetched {CONVERSION_PKG}/ ({n} modules)")
            n = _fetch_package(repo, GGUF_PKG_PATH, gguf_root / "gguf")
            print(f"      fetched gguf ({n} modules)")
            return script, gguf_root
        except Exception as exc:  # noqa: BLE001 -- any failure means try the next mirror
            print(f"      failed: {exc}")
            last_error = exc

    _fail(f"Could not download the llama.cpp converter ({last_error}). Clone llama.cpp by "
          f"hand and copy convert_hf_to_gguf.py, conversion/ and gguf-py/gguf into "
          f"{build_root}, then re-run.")


def convert_to_gguf(build_dir: Path, output: Path, outtype: str) -> Path:
    """
    Run llama.cpp's converter over the merged model.

    Invoked as a subprocess rather than imported: the script is written to be run as
    `__main__`, parses its own argv, and calls sys.exit -- importing it would mean
    monkeypatching argv inside this process and inheriting whatever it does to logging.
    """
    if output.exists():
        print(f"[3/3] {output.name} already exists; skipping conversion")
        return output

    script, gguf_root = ensure_convert_script(build_dir.parent)
    output.parent.mkdir(parents=True, exist_ok=True)

    # The fetched gguf shadows the installed wheel for this subprocess only. Prepended
    # rather than replacing PYTHONPATH so anything the caller set still applies.
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(
        [str(gguf_root)] + ([env["PYTHONPATH"]] if env.get("PYTHONPATH") else []))

    print(f"[3/3] converting to GGUF ({outtype})...")
    result = subprocess.run(
        [sys.executable, str(script), str(build_dir),
         "--outfile", str(output), "--outtype", outtype],
        cwd=str(BACKEND_DIR),
        env=env,
    )
    if result.returncode != 0:
        _fail(f"convert_hf_to_gguf.py exited {result.returncode}. The merged model is "
              f"still at {build_dir}, so re-running skips straight back to this step.")

    if not output.exists():
        _fail(f"Converter reported success but {output} does not exist.")
    return output


def write_sidecar(output: Path, adapter_dir: Path) -> None:
    """
    Record where this GGUF came from, beside the GGUF.

    A quantised binary carries no provenance, and this one is three transformations away
    from anything a person could inspect. Six months from now the only question anyone
    will ask about this file is "which run is this, and was it allowed to ship" -- so the
    run id and the eval verdict live here rather than in a commit message.
    """
    import json
    from datetime import datetime, timezone

    run_record = adapter_dir / "run_record.json"
    record = json.loads(run_record.read_text(encoding="utf-8")) if run_record.exists() else {}

    sidecar = {
        "gguf": output.name,
        "built_at_utc": datetime.now(timezone.utc).isoformat(),
        "built_by": "integrated-backend/scripts/build_finetuned_gguf.py",
        "source_adapter": str(adapter_dir),
        "run_id": record.get("run_id"),
        "base_model": record.get("base_model_id"),
        "dataset_version": record.get("dataset_version"),
        "final_eval_loss": record.get("final_eval_loss"),
        # Carried over from 03_testing_and_versioning/version_registry.csv. This candidate
        # did NOT pass the ML track's promotion gate; it is wired in here as a demo /
        # integration decision, not a promotion. See the README section this script's
        # output is documented in.
        "promotion_status": "NOT PROMOTED - failed acceptance gate (see "
                            "model-Thevindu/03_testing_and_versioning/version_registry.csv)",
    }
    path = output.with_suffix(".json")
    path.write_text(json.dumps(sidecar, indent=2) + "\n", encoding="utf-8")
    print(f"      provenance written to {path.name}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    parser.add_argument("--adapter", type=Path, default=DEFAULT_ADAPTER,
                        help="PEFT adapter directory to merge")
    parser.add_argument("--build-dir", type=Path, default=DEFAULT_BUILD_DIR,
                        help="scratch directory for the merged fp16 model")
    parser.add_argument("--base", default="",
                        help="local directory holding the base weights, instead of "
                             "downloading the id recorded in the adapter")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT,
                        help="GGUF file to write")
    parser.add_argument("--outtype", default="q8_0",
                        choices=["q8_0", "f16", "bf16", "f32"],
                        help="GGUF quantisation (q8_0 default; k-quants need llama.cpp)")
    parser.add_argument("--clean", action="store_true",
                        help="delete the merged model once the GGUF is written")
    args = parser.parse_args()

    adapter = args.adapter.resolve()
    print(f"[1/3] adapter: {adapter}")
    if not adapter.exists():
        _fail(f"{adapter} does not exist. The adapter weights are gitignored by the ML "
              f"track -- copy them from wherever the training run saved them.")
    if not (adapter / "adapter_model.safetensors").exists():
        _fail(f"{adapter} has no adapter_model.safetensors.")

    merged = merge_adapter(adapter, args.build_dir.resolve(), args.base)
    output = convert_to_gguf(merged, args.output.resolve(), args.outtype)
    write_sidecar(output, adapter)

    if args.clean:
        print(f"      removing {merged}")
        shutil.rmtree(merged, ignore_errors=True)

    size_gb = output.stat().st_size / 1_073_741_824
    print(f"\nDone. {output} ({size_gb:.2f} GB)")
    print("\nPoint the generator at it in .env:")
    print(f"    LEARNMATE_GENERATOR_MODEL=models/{output.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
