# all the code related to LLM model stay here
"""
LLM layer for the evaluator agent.

The judge runs Llama 3.2 3B Instruct (Q4_K_M GGUF) locally on CPU via llama-cpp-python.
It is deliberately a *different* model family from the generator (Qwen2.5-3B in chat-agent/),
so the judge is not grading its own output style.

The model file is downloaded from Hugging Face on first use into evaluator_agent/models/
and reused from disk afterwards. No API key or billing is required; HF_TOKEN is only read
if present (it lifts anonymous download rate limits).
"""

import json
import os
import re

from dotenv import load_dotenv
from huggingface_hub import hf_hub_download
from llama_cpp import Llama

# Picks up HF_TOKEN from components-Dinura/.env by walking up from this file.
load_dotenv()

# --- Model location -----------------------------------------------------------------

# bartowski's repo is an ungated GGUF conversion of meta-llama/Llama-3.2-3B-Instruct,
# so it downloads without needing access approval on the gated Meta repo.
REPO_ID = os.getenv("EVALUATOR_MODEL_REPO", "bartowski/Llama-3.2-3B-Instruct-GGUF")
FILENAME = os.getenv("EVALUATOR_MODEL_FILE", "Llama-3.2-3B-Instruct-Q4_K_M.gguf")

MODELS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models")

# Judging is a short-output / long-input task: a summary plus its source text has to fit.
DEFAULT_N_CTX = int(os.getenv("EVALUATOR_N_CTX", "8192"))


def ensure_model(repo_id: str = REPO_ID, filename: str = FILENAME) -> str:
    """
    Return a local path to the GGUF file, downloading it on first call (~2 GB).

    Subsequent calls hit the local cache in evaluator_agent/models/ and do no network I/O.
    """
    os.makedirs(MODELS_DIR, exist_ok=True)
    target = os.path.join(MODELS_DIR, filename)

    if not os.path.exists(target):
        print(f"[*] Downloading {filename} from {repo_id} (first run only, ~2 GB)...")

    return hf_hub_download(
        repo_id=repo_id,
        filename=filename,
        local_dir=MODELS_DIR,
        token=os.getenv("HF_TOKEN") or None,
    )


# --- Judging contract ---------------------------------------------------------------

# Constrained decoding: llama.cpp compiles this into a grammar, so the model cannot emit
# prose around the JSON or invent extra keys.
VERDICT_SCHEMA = {
    "type": "object",
    "properties": {
        "score": {"type": "integer", "minimum": 1, "maximum": 100},
        "reasoning": {"type": "string"},
        "regeneration_instruction": {"type": "string"},
    },
    "required": ["score", "reasoning", "regeneration_instruction"],
}

JUDGE_SYSTEM_PROMPT = """You are a strict evaluation model. You grade content produced by another AI.

Rules:
- Score from 1 to 100. Be harsh: 90+ means flawless, 70-89 usable with minor faults, 50-69 clearly weak, below 50 unusable.
- Judge only against the criteria and the material given. Never use outside knowledge to fill gaps.
- If the material is factually unsupported by the source, the score must be below 50.
- "reasoning" is at most 3 short sentences naming the concrete faults you found.
- "regeneration_instruction" is a direct order to the generator model telling it exactly what to fix and keep. Write one complete sentence of at least ten words that names the specific fault and the specific correction. Begin with an imperative verb such as Remove, Rewrite, Add or Replace, but never emit a bare verb or trailing dots: "Rewrite..." is not an instruction and will be rejected. Never write the corrected content itself, and never state a fact that is not in the material you were given: you are instructing a rewrite, not performing it. Write it even when the score is high; it is discarded when the score passes the threshold.
- Reply with JSON only."""

# Fallback criteria used when a task-specific evaluator module has not supplied its own.
# The detailed per-type rubrics live in summary_evaluator.py, mcq_evaluator.py, etc.
DEFAULT_RUBRICS = {
    "summary": "Faithfulness to the source, coverage of its main points, concision, and absence of invented facts.",
    "keypoints": "Each key point must be supported by the source, be distinct from the others, and cover what actually matters in the source.",
    "mcq": "The question is answerable from the source, the marked answer is correct, distractors are plausible but clearly wrong, and exactly one option is right.",
    "practice_qsn": "The answer is correct, complete, and reasoned from the source rather than asserted.",
    "chat_msg": "Relevance to the user's message, coherence with the conversation so far, and informativeness without padding.",
    "generic": "Correctness, relevance to the given material, completeness, and clarity.",
}

DEFAULT_THRESHOLD = int(os.getenv("EVALUATOR_THRESHOLD", "70"))


class EvaluatorLLM:
    """
    Local Llama 3.2 3B judge.

    One Llama instance per (model_path, n_ctx) is shared across every evaluator module,
    so loading the ~2 GB model into RAM happens once per process no matter how many
    evaluators are constructed.
    """

    _models = {}

    def __init__(self, model_path: str = None, n_ctx: int = DEFAULT_N_CTX, n_threads: int = None):
        model_path = model_path or ensure_model()
        key = (model_path, n_ctx)

        if key not in EvaluatorLLM._models:
            print(f"[*] Loading evaluator model: {os.path.basename(model_path)} (first load only)...")
            EvaluatorLLM._models[key] = Llama(
                model_path=model_path,
                n_ctx=n_ctx,
                n_threads=n_threads,  # None -> llama.cpp auto-detects CPU cores
                verbose=False,
            )

        self.model_path = model_path
        self.n_ctx = n_ctx
        self.model = EvaluatorLLM._models[key]

    def chat(self, messages, max_tokens: int = 512, temperature: float = 0.0, schema: dict = None) -> str:
        """Raw chat call. Passing `schema` forces the reply to match that JSON schema."""
        kwargs = {
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if schema is not None:
            kwargs["response_format"] = {"type": "json_object", "schema": schema}

        result = self.model.create_chat_completion(**kwargs)
        return result["choices"][0]["message"]["content"]

    def judge(
        self,
        task: str,
        generated: str,
        source: str = None,
        criteria: str = None,
        threshold: int = DEFAULT_THRESHOLD,
        max_tokens: int = 512,
    ) -> dict:
        """
        Score one generated artefact and say how to regenerate it.

        task      -- key into DEFAULT_RUBRICS ("summary", "mcq", ...); also echoed in the result
        generated -- the content being graded
        source    -- the material it must be faithful to (source text, chat context, ...); optional
        criteria  -- task-specific rubric; overrides DEFAULT_RUBRICS[task]
        threshold -- scores below this are marked for regeneration

        Returns:
            {task, score, passed, reasoning, regeneration_instruction, threshold}

        `regeneration_instruction` is emptied when the score passes, so callers can simply
        check `passed` or test the instruction for truthiness.
        """
        criteria = criteria or DEFAULT_RUBRICS.get(task, DEFAULT_RUBRICS["generic"])

        parts = [f"Evaluation task: {task}", f"Criteria:\n{criteria}"]
        if source:
            parts.append(f"SOURCE MATERIAL:\n\"\"\"\n{source}\n\"\"\"")
        parts.append(f"CONTENT TO EVALUATE:\n\"\"\"\n{generated}\n\"\"\"")
        parts.append(
            'Return JSON with exactly these keys: "score" (integer 1-100), '
            '"reasoning" (string), "regeneration_instruction" (string).'
        )

        messages = [
            {"role": "system", "content": JUDGE_SYSTEM_PROMPT},
            {"role": "user", "content": "\n\n".join(parts)},
        ]

        raw, failure = None, None
        try:
            raw = self.chat(messages, max_tokens=max_tokens, temperature=0.0, schema=VERDICT_SCHEMA)
        except Exception:
            # Older llama-cpp-python builds without grammar-constrained JSON: ask plainly
            # and lean on _parse_verdict to pull the object out of whatever comes back.
            try:
                raw = self.chat(messages, max_tokens=max_tokens, temperature=0.0)
            except Exception as exc:
                # Both attempts died the same way (context overflow, OOM, bad model file).
                # Fail closed like _parse_verdict does rather than taking the caller's turn
                # down: the orchestrator is mid-conversation and needs a verdict, not a stack
                # trace. The reason travels in `reasoning`, so the failure stays visible.
                failure = f"{type(exc).__name__}: {exc}"

        if failure is not None:
            verdict = {
                "score": 1,
                "reasoning": f"Evaluator could not run: {failure}",
                "regeneration_instruction": "Regenerate the content; the evaluator failed to return a verdict.",
            }
        else:
            verdict = _parse_verdict(raw)
        verdict["task"] = task
        verdict["threshold"] = threshold
        verdict["passed"] = verdict["score"] >= threshold
        if verdict["passed"]:
            verdict["regeneration_instruction"] = ""

        return verdict


# A bare verb, optionally trailing dots: the judge echoing the prompt's example rather than
# writing an order. Anything this matches carries no information for the generator.
_BARE_VERB = re.compile(r"^(remove|rewrite|add|replace|revise|correct|fix)?[\s.…]*$", re.IGNORECASE)

# Shorter than this and an "instruction" cannot name both a fault and a correction.
_MIN_INSTRUCTION_CHARS = 20


def _usable_instruction(instruction: str, reasoning: str) -> str:
    """
    Guarantee the reflection loop has something to act on.

    A 3B judge intermittently answers with the example verb from the system prompt
    ("Rewrite...") instead of an actual order. Regenerating on that is strictly worse than
    not regenerating: the generator gets no signal and tends to collapse into a vaguer
    answer. The reasoning field does describe the fault, so fall back to it.
    """
    instruction = (instruction or "").strip()
    if len(instruction) >= _MIN_INSTRUCTION_CHARS and not _BARE_VERB.match(instruction):
        return instruction

    reasoning = (reasoning or "").strip()
    if reasoning:
        return f"Fix exactly this problem and change nothing else: {reasoning}"
    return "Regenerate the content; the evaluator returned no usable instruction."


def _parse_verdict(raw: str) -> dict:
    """Turn the model's reply into a verdict dict, tolerating stray prose or code fences."""
    data = None
    try:
        data = json.loads(raw)
    except (ValueError, TypeError):
        match = re.search(r"\{.*\}", raw or "", re.DOTALL)
        if match:
            try:
                data = json.loads(match.group(0))
            except ValueError:
                data = None

    if not isinstance(data, dict):
        # A judge that cannot be parsed must not silently pass content through.
        return {
            "score": 1,
            "reasoning": f"Could not parse evaluator output: {(raw or '').strip()[:200]}",
            "regeneration_instruction": "Regenerate the content; the evaluator returned an unreadable verdict.",
        }

    try:
        score = int(float(data.get("score", 1)))
    except (TypeError, ValueError):
        score = 1

    reasoning = str(data.get("reasoning", "")).strip()

    return {
        "score": max(1, min(100, score)),
        "reasoning": reasoning,
        "regeneration_instruction": _usable_instruction(
            str(data.get("regeneration_instruction", "")), reasoning),
    }
