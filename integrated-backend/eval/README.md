# Evaluation harness

Every number in `paper/` is produced here. Scripts write JSON with provenance (commit,
dirty flag, machine, package versions, settings) under `data/eval_results/`, and
`python -m eval.tables` turns those files into `paper/tables/*.tex` and the
`\val{...}` numbers quoted in the text.

All commands run from `integrated-backend/` with the venv active.

## Isolation

`eval.common.bootstrap()` points the engine at stores the app never uses:

| | Evaluation | App |
|---|---|---|
| MongoDB | database `learnmate_eval` (same server, :27018) | `learnmate` |
| Qdrant | container `learnmate-eval-qdrant` on 127.0.0.1:6337 | :6335 / deploy stack |
| Generator | Qwen2.5-3B (registry default) | whatever `.env` says |

Start the eval Qdrant once:

```
docker run -d --name learnmate-eval-qdrant --restart unless-stopped \
  -p 127.0.0.1:6337:6333 -v learnmate_eval_qdrant:/qdrant/storage qdrant/qdrant:v1.18.1
```

## Order

```
python -m eval.corpus fetch          # the textbook, from the LibreTexts mirror
python -m eval.corpus split          # textbook -> 8 chapter PDFs (data/eval_corpus/docs)
python -m eval.corpus ingest         # through the app's own ingestion, v2 collection
python -m eval.workload generate     # LLM-written questions (slow: ~30-50 s each on CPU)
python -m eval.workload sessions     # 40 simulated students, Zipf over questions
python -m eval.ir_bench              # retrieval quality + latency per strategy
python -m eval.ir_scaling            # in-process vs server-side BM25 as documents grow
python -m eval.cache_bench           # cache hit precision/recall vs thresholds
python -m eval.chat_latency          # full turns: miss vs hit (needs the models)
python -m eval.cache_replay          # hit rate over the simulated fortnight
python -m eval.heatmap_bench         # topic mining / page attribution quality
python scripts/serve/probe.py --out data/eval_results/serving/probe.json   # llama-server
python -m eval.load_test --label pool_cache ...                          # running API
python -m eval.tables                # -> paper/tables
```

The corpus is *Business Law I Essentials* (OpenStax, 2019), in its LibreTexts edition,
licensed CC BY-NC-SA 4.0. It is fetched by `eval/corpus.py`, not committed. Latency numbers
are only comparable within one machine, and every result file records which machine it
came from.
