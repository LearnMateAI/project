# 02 — Judges

Drop-ins for live **Llama-3.2-3B-Instruct Q4**. Never the same family as the generator under test.

| Folder | Model |
|--------|--------|
| [llama32-3b](llama32-3b/) | Llama 3.2 3B Instruct (live baseline) |
| [gemma2-2b](gemma2-2b/) | Same GGUF as the generator candidate; judge role only |
| [granite-2b](granite-2b/) | Granite 3.2 2B Instruct |

Each folder has Dinura-style `evaluator/judge.py` that injects that GGUF into the live `Judge` class. Pair only with Qwen (or Phi). Run:

```powershell
.\venv\Scripts\python.exe ..\thevindu-models\scripts\eval_components.py --judges llama32-3b granite-2b gemma2-2b-judge
```
