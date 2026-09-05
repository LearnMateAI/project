# Llama 3.2 3B Instruct — live judge baseline

**Role:** the judge already in `.env`. Same `evaluator/` filenames as Granite and Gemma-judge.

Never load Llama as generator and judge in one process. Pair with Qwen, Gemma, or Phi as the generator.

```powershell
cd integrated-backend
.\venv\Scripts\python.exe ..\thevindu-models\scripts\eval_components.py --judges llama32-3b
```
