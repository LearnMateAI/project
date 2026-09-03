# Gemma 2 2B Instruct — `model-gemma2-2b`

**Role:** generator candidate A (vs live Qwen2.5-3B-Instruct Q4).  
**Same GGUF may also be used as a judge**, but never as generator **and** judge in one process.

| | |
|--|--|
| Original | `google/gemma-2-2b-it` |
| GGUF we run | `bartowski/gemma-2-2b-it-GGUF` / `gemma-2-2b-it-Q4_K_M.gguf` (~1.71 GB) |
| Family | Gemma 2 — not Qwen, not Llama |
| Licence | Gemma (acknowledge on some HF repos; Bartowski GGUF is the file we fetch) |
| Live default? | **No.** `experimental: true` in `models_registry.yaml` |

## Why this model (not another Qwen)

The 1.5B Qwen LoRA already failed the legal gate. Another Qwen size would not tell us whether a **different pretrain** is better at instruction-following JSON on a laptop. Gemma 2 2B is the smallest widely used instruct model in the same Q4 band, with a sliding-window architecture and a different tokenizer/template. If it wins, that is an architecture win. If it loses, we keep Qwen 3B for a real reason.

Risks: some templates reject a system turn (put instructions in the user message). 2B may be weaker on long IRAC than 3B. Do not pair Gemma-generator with Gemma-judge.

## Files (weights are gitignored)

```
model-gemma2-2b/
  README.md          this file
```

The GGUF lands at `integrated-backend/models/gemma-2-2b-it-Q4_K_M.gguf` after fetch.

## 1. Fetch (once)

From `integrated-backend`, backend venv:

```powershell
.\venv\Scripts\python.exe ..\docs\thevindu-models\scripts\fetch_comparison_models.py --gguf gemma2-2b
```

Needs disk for ~1.71 GB plus HF cache. Optional `HF_TOKEN` in `.env` if rate-limited.

## 2. Smoke / score against Qwen

```powershell
.\venv\Scripts\python.exe ..\docs\thevindu-models\scripts\eval_gguf.py --generators qwen25-3b gemma2-2b
```

Metrics: grounded substring hits on `docs/thevindu-models/fixtures/generator_prompts.jsonl`, JSON validity on the MCQ item, mean latency. Qwen is skipped too if its GGUF is missing.

As **judge only** (generator must be Qwen or Phi in that pairing):

```powershell
.\venv\Scripts\python.exe ..\docs\thevindu-models\scripts\eval_gguf.py --judges llama32-3b gemma2-2b-judge
```

## 3. Wire into the live app (explicit `model_id`, not silent default)

Already listed in `integrated-backend/learnmate/models_registry.yaml` as `gemma2-2b` with `experimental: true`. The UI can select it once the GGUF exists (`available` is file-on-disk). Restart the backend after the download.

To force it as the process fallback (do this only after RESULTS.md says so):

```
LEARNMATE_GENERATOR_MODEL=models/gemma-2-2b-it-Q4_K_M.gguf
LEARNMATE_GENERATOR_REPO=bartowski/gemma-2-2b-it-GGUF
LEARNMATE_GENERATOR_FILE=gemma-2-2b-it-Q4_K_M.gguf
LEARNMATE_GENERATOR_CHAT_FORMAT=
```

Leave `chat_format` empty so llama.cpp reads GGUF metadata.

To use this GGUF as **judge** instead (generator stays Qwen):

```
LEARNMATE_JUDGE_MODEL=models/gemma-2-2b-it-Q4_K_M.gguf
LEARNMATE_JUDGE_REPO=bartowski/gemma-2-2b-it-GGUF
LEARNMATE_JUDGE_FILE=gemma-2-2b-it-Q4_K_M.gguf
```

## 4. What “better” means

Beat Qwen on grounded hit rate **and** JSON validity on the fixture, without a large latency regression on this laptop. A win on train loss or a public IFEval screenshot is not enough. See `docs/thevindu-models/RESEARCH.md`.
