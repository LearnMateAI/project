"""One-shot writer for per-model chat_agent / evaluator / testing files."""

from __future__ import annotations

from pathlib import Path

HUB = Path(__file__).resolve().parent.parent


GENERATORS = [
    {
        "folder": HUB / "01_generators" / "qwen25-3b",
        "id": "qwen25-3b",
        "name": "Qwen 2.5 3B Instruct",
        "role": "generator",
        "baseline": True,
        "gguf": "qwen2.5-3b-instruct-q4_k_m.gguf",
        "registry_id": "qwen25-3b",
        "pair": "llama32-3b",
    },
    {
        "folder": HUB / "01_generators" / "gemma2-2b",
        "id": "gemma2-2b",
        "name": "Gemma 2 2B Instruct",
        "role": "generator",
        "baseline": False,
        "gguf": "gemma-2-2b-it-Q4_K_M.gguf",
        "registry_id": "gemma2-2b",
        "pair": "llama32-3b",
    },
    {
        "folder": HUB / "01_generators" / "phi35-mini",
        "id": "phi35-mini",
        "name": "Phi-3.5 Mini Instruct",
        "role": "generator",
        "baseline": False,
        "gguf": "Phi-3.5-mini-instruct-Q4_K_M.gguf",
        "registry_id": "phi35-mini",
        "pair": "llama32-3b",
    },
]

JUDGES = [
    {
        "folder": HUB / "02_judges" / "llama32-3b",
        "id": "llama32-3b",
        "name": "Llama 3.2 3B Instruct",
        "role": "judge",
        "baseline": True,
        "gguf": "Llama-3.2-3B-Instruct-Q4_K_M.gguf",
        "registry_id": None,
        "pair": "qwen25-3b",
    },
    {
        "folder": HUB / "02_judges" / "gemma2-2b",
        "id": "gemma2-2b-judge",
        "name": "Gemma 2 2B Instruct (judge role)",
        "role": "judge",
        "baseline": False,
        "gguf": "gemma-2-2b-it-Q4_K_M.gguf",
        "registry_id": None,
        "pair": "qwen25-3b",
    },
    {
        "folder": HUB / "02_judges" / "granite-2b",
        "id": "granite-2b",
        "name": "Granite 3.2 2B Instruct",
        "role": "judge",
        "baseline": False,
        "gguf": "ibm-granite_granite-3.2-2b-instruct-Q4_K_M.gguf",
        "registry_id": None,
        "pair": "qwen25-3b",
    },
]

EMBEDDINGS = [
    {
        "folder": HUB / "03_embeddings" / "minilm-l6",
        "id": "minilm-l6",
        "name": "all-MiniLM-L6-v2",
        "hf": "all-MiniLM-L6-v2",
        "baseline": True,
    },
    {
        "folder": HUB / "03_embeddings" / "bge-small",
        "id": "bge-small",
        "name": "BGE-small-en-v1.5",
        "hf": "BAAI/bge-small-en-v1.5",
        "baseline": False,
    },
    {
        "folder": HUB / "03_embeddings" / "e5-small",
        "id": "e5-small",
        "name": "E5-small-v2",
        "hf": "intfloat/e5-small-v2",
        "baseline": False,
    },
]


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def generator_files(m: dict) -> None:
    mid, name, gguf, rid, pair = m["id"], m["name"], m["gguf"], m["registry_id"], m["pair"]
    root = m["folder"]
    write(root / "chat_agent" / "__init__.py", f'"""Live chat_agent bound to {mid}."""\nMODEL_ID = {rid!r}\n')
    write(root / "chat_agent" / "generate.py", f'''"""
Replace the previous generator with {name}.

Same file as components-Dinura/learnmate/chat_agent/generate.py and
integrated-backend/learnmate/chat_agent/generate.py. Only model_id changes.
Pair only with {pair} as judge. Never the same family in one process.
"""

MODEL_ID = {rid!r}
GGUF = {gguf!r}

from learnmate.chat_agent.generate import generate_node as live_generate_node


def generate_node(state):
    return live_generate_node({{**state, "model_id": MODEL_ID}})
''')
    write(root / "chat_agent" / "evaluate.py", f'''"""
Evaluate a {name} reply with the live judge ({pair}).

Does not load this GGUF as judge. Same evaluate_node as the fully-wired app.
"""

PAIR_JUDGE = {pair!r}

from learnmate.chat_agent.evaluate import evaluate_node
from learnmate.evaluator.judge import Judge

__all__ = ["evaluate_node", "Judge", "PAIR_JUDGE"]
''')
    write(root / "chat_agent" / "prompts.py", '''"""Live chat prompts — not a per-model fork."""

from learnmate.chat_agent.prompts import GENERAL_SYSTEM, GROUNDED_SYSTEM, REWRITE_SYSTEM

__all__ = ["GROUNDED_SYSTEM", "GENERAL_SYSTEM", "REWRITE_SYSTEM"]
''')
    write(root / "evaluator" / "__init__.py", f'"""Gate 1 validators + live Judge. Generator {mid} is not the judge."""\n')
    write(root / "evaluator" / "judge.py", f'''"""Live Judge. This folder is a generator; the judge stays {pair}."""

PAIR_JUDGE = {pair!r}

from learnmate.evaluator.judge import Judge, get_judge

__all__ = ["Judge", "get_judge", "PAIR_JUDGE"]
''')
    write(root / "evaluator" / "rubrics.py", '''"""Live rubrics."""

from learnmate.evaluator.rubrics import for_task

__all__ = ["for_task"]
''')
    write(root / "evaluator" / "validators.py", '''"""Live Gate 1 — used for the MCQ drop-in check."""

from learnmate.evaluator.validators import validate

__all__ = ["validate"]
''')
    role_line = "baseline generator" if m["baseline"] else "generator candidate"
    write(root / "acceptance_thresholds.yaml", f'''# Per-model copy of testing/acceptance_thresholds.yaml ({mid})
candidate_id: {mid}
role: generator
baseline: {str(m["baseline"]).lower()}
both_required: true
pair_judge: {pair}
''')
    write(root / "promotion_checklist.md", f'''# Promotion checklist — {name}

See `thevindu-models/testing/promotion_checklist.md`. Candidate `{mid}` ({role_line}).

- [ ] GGUF `{gguf}` on disk, magic `GGUF`
- [ ] `eval_components.py --generators {mid}` completed, not skipped
- [ ] Beats Qwen on **both** grounded hits and JSON validity (or is the Qwen baseline)
- [ ] `.env` / `selectable_default` unchanged
- [ ] Four-eyes review
''')
    write(root / "model_card.md", f'''# Model card — {name}

| Field | Value |
|-------|-------|
| Id | `{mid}` |
| Role | generator ({role_line}) |
| GGUF | `{gguf}` |
| Live component | `integrated-backend/learnmate/chat_agent/generate.py` |
| Pair judge | `{pair}` |
| `selectable_default` | **not changed** |
| Card status | See `RESULTS.md` in this folder |

Intended use: study Q&A and MCQ JSON on a laptop CPU. Out of scope: legal advice.
''')
    write(root / "version_registry.csv", "candidate_id,role,passed,measured,verdict\n")
    write(root / "RESULTS.md", f'''# RESULTS — {name}

**Machine:** this Windows laptop CPU.  
**Component path:** live `chat_agent.generate_node` + `resource_agent` MCQ + Gate 1 `validate`.  
**Not** a uvicorn chat p95. `.env` was not edited.

| Metric | Value | Source |
|--------|-------|--------|
| Grounded hits | _pending `eval_components.py`_ | `results/components.json` |
| JSON validity | _pending_ | live MCQ schema + `validate("mcq")` |
| Mean ms | _pending_ | this laptop |

**Verdict:** _fill after the component run. Phi/Gemma must beat Qwen on both metrics._
''')
    readme = root / "README.md"
    if not readme.is_file():
        write(readme, f"# {name} — `{mid}`\n\nSee `chat_agent/` and `evaluator/` (live component swap).\n")


def judge_files(m: dict) -> None:
    mid, name, gguf, pair = m["id"], m["name"], m["gguf"], m["pair"]
    root = m["folder"]
    write(root / "chat_agent" / "__init__.py", f'"""Judge package {mid}: generate stays {pair}."""\nPAIR_GENERATOR = {pair!r}\n')
    write(root / "chat_agent" / "generate.py", f'''"""
Do not load `{mid}` as the generator in the same process as this judge.

The live generate_node stays on `{pair}`.
"""

PAIR_GENERATOR = {pair!r}

from learnmate.chat_agent.generate import generate_node

__all__ = ["generate_node", "PAIR_GENERATOR"]
''')
    write(root / "chat_agent" / "evaluate.py", f'''"""
Replace the previous judge with {name}.

Same evaluate_node as integrated-backend. The bake-off injects this GGUF into
`Judge(llm=...)` so LEARNMATE_JUDGE_MODEL is not edited.
"""

MODEL_ID = {mid!r}
GGUF = {gguf!r}
PAIR_GENERATOR = {pair!r}

from learnmate.chat_agent.evaluate import evaluate_node

__all__ = ["evaluate_node", "MODEL_ID", "GGUF", "PAIR_GENERATOR"]
''')
    write(root / "chat_agent" / "prompts.py", '''"""Live chat prompts."""

from learnmate.chat_agent.prompts import GENERAL_SYSTEM, GROUNDED_SYSTEM, REWRITE_SYSTEM

__all__ = ["GROUNDED_SYSTEM", "GENERAL_SYSTEM", "REWRITE_SYSTEM"]
''')
    write(root / "evaluator" / "__init__.py", f'"""Live evaluator bound to {mid}."""\n')
    write(root / "evaluator" / "judge.py", f'''"""
Same job as components-Dinura/learnmate/evaluator/judge.py.

Builds the live Judge around `{gguf}` without changing `.env`.
"""

MODEL_ID = {mid!r}
GGUF = {gguf!r}
PAIR_GENERATOR = {pair!r}

from pathlib import Path

from learnmate.evaluator.judge import Judge
from learnmate.llm.llamacpp import LlamaCppChatModel
from learnmate import config


def get_candidate_judge(threshold: int = 70) -> Judge:
    path = Path(config.MODELS_DIR) / GGUF
    llm = LlamaCppChatModel(
        gguf_path=str(path),
        n_ctx=8192,
        chat_format=None,
        temperature=0.0,
        max_tokens=512,
    )
    return Judge(llm=llm, threshold=threshold)
''')
    write(root / "evaluator" / "rubrics.py", '''"""Live rubrics — CHAT_GROUNDED is what judge_gold is scored against."""

from learnmate.evaluator.rubrics import CHAT_GROUNDED, for_task

__all__ = ["CHAT_GROUNDED", "for_task"]
''')
    write(root / "evaluator" / "prompt.py", '''"""Live judge prompt (includes SystemMessage — a drop-in must accept it)."""

from learnmate.evaluator.prompt import SYSTEM_PROMPT, build_messages, build_chat_source

__all__ = ["SYSTEM_PROMPT", "build_messages", "build_chat_source"]
''')
    write(root / "evaluator" / "verdict.py", '''"""Live fail-closed verdict parsing."""

from learnmate.evaluator.verdict import VERDICT_SCHEMA, failed_verdict, parse_verdict

__all__ = ["VERDICT_SCHEMA", "failed_verdict", "parse_verdict"]
''')
    role_line = "baseline judge" if m["baseline"] else "judge candidate"
    write(root / "acceptance_thresholds.yaml", f'''candidate_id: {mid}
role: judge
baseline: {str(m["baseline"]).lower()}
agreement_must_match_or_beat_baseline: true
system_role_required: true
pair_generator: {pair}
large_latency_regression: 0.25
''')
    write(root / "promotion_checklist.md", f'''# Promotion checklist — {name}

Candidate `{mid}` ({role_line}). Pair only with `{pair}`.

- [ ] GGUF `{gguf}` magic `GGUF`
- [ ] `eval_components.py --judges {mid}` completed
- [ ] Matches/beats Llama on gold agreement, no large latency regression
- [ ] Accepts `SystemMessage` (live evaluate_node always sends one)
- [ ] `.env` unchanged
- [ ] Four-eyes
''')
    write(root / "model_card.md", f'''# Model card — {name}

| Field | Value |
|-------|-------|
| Id | `{mid}` |
| Role | judge ({role_line}) |
| GGUF | `{gguf}` |
| Live component | `integrated-backend/learnmate/evaluator/judge.py` |
| Pair generator | `{pair}` |
| `selectable_default` | **not changed** |
''')
    write(root / "version_registry.csv", "candidate_id,role,passed,measured,verdict\n")
    write(root / "RESULTS.md", f'''# RESULTS — {name}

**Machine:** this Windows laptop CPU.  
**Component path:** live `evaluator.Judge` (SystemMessage + CHAT_GROUNDED + fail-closed verdict).  
**Pair generator:** `{pair}` (not loaded in the same-family process).

| Metric | Value | Source |
|--------|-------|--------|
| Gold-label agreement | _pending `eval_components.py`_ | `results/components.json` |
| Mean ms | _pending_ | this laptop |
| System role | _pending_ | live prompt.py |

**Verdict:** _Granite must match/beat Llama without a large latency regression. Gemma must accept SystemMessage._
''')
    if not (root / "README.md").is_file():
        write(root / "README.md", f"# {name} — `{mid}`\n\nJudge drop-in. Pair with `{pair}` only.\n")


def embedding_files(m: dict) -> None:
    mid, name, hf = m["id"], m["name"], m["hf"]
    root = m["folder"]
    write(root / "chat_agent" / "__init__.py", f'"""Retrieve-side swap for {mid}. Generate/judge stay live Qwen/Llama."""\n')
    write(root / "chat_agent" / "retrieve.py", f'''"""
Replace the previous embedder with {name} for in-memory retrieve only.

Same retrieve contract as components-Dinura/learnmate/chat_agent/retrieve.py.
Does **not** write Qdrant. Mixed MiniLM/E5/BGE collections are undefined.
"""

HF_ID = {hf!r}
MODEL_ID = {mid!r}

from learnmate.chat_agent.retrieve import retrieve_node

__all__ = ["retrieve_node", "HF_ID", "MODEL_ID"]
''')
    write(root / "evaluator" / "__init__.py", '"""Retrieve candidates are not judges. Live Judge stays Llama."""\n')
    write(root / "acceptance_thresholds.yaml", f'''candidate_id: {mid}
role: embeddings
baseline: {str(m["baseline"]).lower()}
primary_fixture: real_pdf
promote_if_toy_wins_and_real_loses: false
dim: 384
''')
    write(root / "promotion_checklist.md", f'''# Promotion checklist — {name}

- [ ] Scored on `Company-law-part1-notes.pdf` (not only the toy fixture)
- [ ] 384-d, prefixes applied through `LearnMateEmbeddings`
- [ ] No Qdrant write / no `.env` flip
- [ ] Four-eyes
''')
    write(root / "model_card.md", f'''# Model card — {name}

| Field | Value |
|-------|-------|
| Id | `{mid}` |
| HF | `{hf}` |
| Role | embeddings |
| Live component | `learnmate/llm/embeddings.py` + `chat_agent/retrieve.py` |
''')
    write(root / "version_registry.csv", "candidate_id,role,passed,measured,verdict\n")
    write(root / "RESULTS.md", f'''# RESULTS — {name}

**Machine:** this Windows laptop CPU.  
**Primary fixture:** real company-law PDF (`results/real_pdf.json`). Toy fixture is history only.

See hub `RESULTS.md` §6 for the numbers. Do not re-ingest unless that section says so.
''')
    if not (root / "README.md").is_file():
        write(root / "README.md", f"# {name}\n\nEmbedding drop-in. Real-PDF verdict only.\n")


def rag_files() -> None:
    root = HUB / "04_rag" / "rerank-and-agents"
    write(root / "chat_agent" / "retrieve.py", '''"""
Live retrieve node. Hybrid vs ANN is LEARNMATE_HYBRID_BM25 in the app;
this bake-off scores both in memory via eval_retrieval.py / eval_real_pdf.py.
"""

from learnmate.chat_agent.retrieve import retrieve_node

__all__ = ["retrieve_node"]
''')
    write(root / "acceptance_thresholds.yaml", '''role: reranker_and_agents
primary_fixture: real_pdf
candidates: [minilm-l12, bge-reranker-base, ann-rerank, hybrid-rerank]
''')
    write(root / "promotion_checklist.md", '''# Promotion checklist — rerankers and retrieve agents

- [ ] Real-PDF table, not toy fixture, drives the call
- [ ] Hybrid BM25 keep-rate inspected (`retrieval_mix`)
- [ ] `.env` not flipped
''')
    write(root / "model_card.md", '''# Model card — MiniLM-L-12 / BGE reranker / hybrid agent

Live components: `learnmate/llm/rerank.py`, `learnmate/chat_agent/retrieve.py`.
''')
    write(root / "RESULTS.md", '''# RESULTS — rerankers and agents

Primary evidence: `thevindu-models/results/real_pdf.json` and hub `RESULTS.md` §6.
L-12 tied L-6 on the real PDF at 2× latency — reject as default.
Hybrid kept one BM25-only chunk — leave hybrid on.
''')


def main() -> None:
    for m in GENERATORS:
        generator_files(m)
    for m in JUDGES:
        judge_files(m)
    for m in EMBEDDINGS:
        embedding_files(m)
    rag_files()
    print("wrote per-model packages")


if __name__ == "__main__":
    main()
