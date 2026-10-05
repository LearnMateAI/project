"""
The evaluation harness behind the demo paper (paper/). Every number the paper reports is
produced by a script in this package and written, with provenance, under
data/eval_results/; eval/tables.py turns those files into the paper's LaTeX tables.

    corpus.py        open-licensed study documents -> the eval database
    workload.py      a synthetic class: questions, paraphrases, near-misses, sessions
    ir_bench.py      retrieval quality and latency, per strategy          (Section 5.1)
    ir_scaling.py    lexical retrieval latency as documents grow           (Section 5.1)
    cache_bench.py   answer-cache decisions: precision/recall vs threshold (Section 5.2)
    cache_replay.py  hit rate as a class asks questions over two weeks     (Section 5.2)
    chat_latency.py  full-pipeline turn latency, cache hit vs miss          (Section 5.2)
    load_test.py     throughput / tail latency under concurrent students   (Section 5.3)
    heatmap_bench.py topic mining and page attribution quality            (Section 5.4)
    tables.py        results -> paper/tables/*.tex

Run from integrated-backend/ with the venv active, e.g. `python -m eval.ir_bench`.
"""
