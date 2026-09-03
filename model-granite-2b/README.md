# Granite 3.2 2B Instruct — `model-granite-2b`

**Role:** judge candidate B (vs live Llama-3.2-3B-Instruct Q4).  
Not registered as a generator. The judge must stay a different family from the live generator.

| | |
|--|--|
| Original | `ibm-granite/granite-3.2-2b-instruct` |
| GGUF we run | `bartowski/ibm-granite_granite-3.2-2b-instruct-GGUF` / `ibm-granite_granite-3.2-2b-instruct-Q4_K_M.gguf` (~1.55 GB) |
| Family | Granite (IBM) |
| Licence | Apache-2.0 |
| Live default? | **No.** |

## Why this model

The judge’s job is to grade against a passage, not to invent law. Granite instruct models are trained to stay on provided documents. 2B Q4 is the smallest of our GGUF candidates, which matters because the judge is the slow second model on CPU. Apache-2.0 is straightforward for coursework. Different family from Qwen, Gemma, and Phi.

Risks: chat template is Granite-specific — leave `chat_format` empty. 2B may be softer than Llama 3.2 3B on “unsupported claim = fail”; that is exactly what `fixtures/judge_gold.jsonl` measures.

Do not use Granite as generator and judge together.

## 1. Fetch (once)

```powershell
cd integrated-backend
.\venv\Scripts\python.exe ..\docs\thevindu-models\scripts\fetch_comparison_models.py --gguf granite-2b
```

## 2. Score against Llama 3.2 (and Gemma-judge if that GGUF exists)

```powershell
.\venv\Scripts\python.exe ..\docs\thevindu-models\scripts\eval_gguf.py --judges llama32-3b granite-2b
```

Accuracy is agreement with gold pass/fail on planted unsupported citations. Latency is secondary.

## 3. Wire as judge (generator stays Qwen unless RESULTS says otherwise)

```
LEARNMATE_JUDGE_MODEL=models/ibm-granite_granite-3.2-2b-instruct-Q4_K_M.gguf
LEARNMATE_JUDGE_REPO=bartowski/ibm-granite_granite-3.2-2b-instruct-GGUF
LEARNMATE_JUDGE_FILE=ibm-granite_granite-3.2-2b-instruct-Q4_K_M.gguf
LEARNMATE_JUDGE_CHAT_FORMAT=
```

Restart the backend. Confirm `/api/health` sees the new judge file. Run one pdf-mode chat turn and check the verdict JSON still has `score`, `reasoning`, `regeneration_instruction`.

## 4. What “better” means

Higher accuracy than Llama 3.2 on `judge_gold.jsonl` without collapsing to “everything passes”. Faster p50 on this laptop is a bonus, not a reason to accept a weaker fail-closed judge.
