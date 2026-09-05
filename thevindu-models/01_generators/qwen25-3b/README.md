# Qwen 2.5 3B Instruct — live generator baseline

**Role:** the generator already in `.env`. This folder exists so the baseline has the same `chat_agent/` + `evaluator/` files as Gemma and Phi.

| | |
|--|--|
| GGUF | `qwen2.5-3b-instruct-q4_k_m.gguf` |
| Live default? | **Yes** (`selectable_default: true`). Do not flip it off from this track. |

`chat_agent/generate.py` calls the live `generate_node` with `model_id=qwen25-3b`. Pair only with Llama or Granite as judge.

```powershell
cd integrated-backend
.\venv\Scripts\python.exe ..\thevindu-models\scripts\eval_components.py --generators qwen25-3b
```
