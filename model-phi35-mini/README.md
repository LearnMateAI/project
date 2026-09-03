# Phi-3.5 Mini Instruct — `model-phi35-mini`

**Role:** generator candidate B (vs live Qwen2.5-3B-Instruct Q4).

| | |
|--|--|
| Original | `microsoft/Phi-3.5-mini-instruct` |
| GGUF we run | `bartowski/Phi-3.5-mini-instruct-GGUF` / `Phi-3.5-mini-instruct-Q4_K_M.gguf` (~2.39 GB) |
| Family | Phi-3 — not Qwen, not Llama, not Gemma |
| Licence | MIT |
| Live default? | **No.** `experimental: true` |

## Why this model

Dense ~3.8B in the same Q4 laptop band as Qwen 3B. Public English instruction numbers sit near older GPT-3.5-class benches; the skill we care about is tight JSON (MCQ options, summaries). MIT is easy for a student project. A different lab and recipe than Gemma, so the two alts are not cousins.

Risks: slightly heavier RAM than Qwen 3B Q4. Chat tokens (`<|user|>`) must come from GGUF metadata — leave `chat_format` empty. Do **not** also use Phi as the judge if Phi wins as generator (same-family grading).

## 1. Fetch (once)

```powershell
cd integrated-backend
.\venv\Scripts\python.exe ..\docs\thevindu-models\scripts\fetch_comparison_models.py --gguf phi35-mini
```

File: `integrated-backend/models/Phi-3.5-mini-instruct-Q4_K_M.gguf`.

## 2. Score against Qwen (and Gemma if both are present)

```powershell
.\venv\Scripts\python.exe ..\docs\thevindu-models\scripts\eval_gguf.py --generators qwen25-3b phi35-mini
```

## 3. Wire into the live app

Registry id `phi35-mini`, experimental. Select in the UI only when `available` is true.

Optional `.env` (not the silent default until RESULTS.md):

```
LEARNMATE_GENERATOR_MODEL=models/Phi-3.5-mini-instruct-Q4_K_M.gguf
LEARNMATE_GENERATOR_REPO=bartowski/Phi-3.5-mini-instruct-GGUF
LEARNMATE_GENERATOR_FILE=Phi-3.5-mini-instruct-Q4_K_M.gguf
LEARNMATE_GENERATOR_CHAT_FORMAT=
```

## 4. What “better” means

Same fixture as Gemma: grounded Q&A hits, MCQ JSON validity, tokens-wall-clock on this machine. Promotion requires beating Qwen on those, then a product pass (chat + one resource job) with Llama or Granite as judge — not Phi as judge.
