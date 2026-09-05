# 01 — Generators

Drop-ins for live **Qwen2.5-3B-Instruct Q4**. Neither is the silent default.

| Folder | Model |
|--------|--------|
| [qwen25-3b](qwen25-3b/) | Qwen 2.5 3B Instruct (live baseline) |
| [gemma2-2b](gemma2-2b/) | Gemma 2 2B Instruct |
| [phi35-mini](phi35-mini/) | Phi-3.5 Mini Instruct |

Each folder has the same `chat_agent/` + `evaluator/` filenames as `components-Dinura` and `integrated-backend`, bound to that GGUF. Run:

```powershell
.\venv\Scripts\python.exe ..\thevindu-models\scripts\eval_components.py --generators qwen25-3b gemma2-2b phi35-mini
```
