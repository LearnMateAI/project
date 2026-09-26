# Golden RAG eval

Offline. No GGUF, Mongo, or Qdrant. The 15-item set is `golden.json`.

```powershell
cd integrated-backend
.\venv\Scripts\python.exe -m eval.golden_rag --compare --out eval/golden_report.json
```

`--profile baseline` replays pre-fix policy (general-knowledge stubs, bare `Context:`, client `evaluate=false` honoured). `--profile current` is F-01/F-02/F-03.

Retrieval is lexical overlap on the fixture pages so CI can fail on a prompt/policy regression without a laptop GPU. For live MiniLM+Qdrant numbers, ingest the fixture text and call `ChatAgent.ask` with `LEARNMATE_ALLOW_CLIENT_EVALUATE=1` only in lab.
