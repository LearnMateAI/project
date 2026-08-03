"""
LLM layer for the resource-generation agent.

Produces study material -- MCQs, practice questions, key points, summaries -- from source
text pulled out of a document. Runs the same Qwen2.5-3B GGUF the chat agent uses, through
the shared LocalInferenceClient, so the weights are loaded once per process rather than a
second 2 GB copy appearing alongside it.

Deliberately a different model family from the evaluator (Llama 3.2 3B): a judge sharing
the generator's weights rates its own output style highly and the reflection loop never
fires.

Each task module (mcq.py, practice_qsn.py, keypoints.py, summary.py) owns its prompt and
its JSON schema. This file owns the model, the retry-with-critique contract, and parsing.
"""

import json
import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_CHAT_AGENT_DIR = os.path.join(os.path.dirname(_HERE), "chat-agent")

# chat-agent/ has a hyphen and so cannot be imported as a package.
for _path in (_HERE, _CHAT_AGENT_DIR):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from local_llm import LocalInferenceClient  # noqa: E402

import keypoints  # noqa: E402
import mcq  # noqa: E402
import practice_qsn  # noqa: E402
import summary  # noqa: E402

GENERATOR_MODEL_PATH = os.path.join(_CHAT_AGENT_DIR, "models", "qwen2.5-3b-instruct-q4_k_m.gguf")

# task name -> module supplying SYSTEM_PROMPT, build_prompt(), SCHEMA, unwrap(), render()
TASKS = {
    "mcq": mcq,
    "practice_qsn": practice_qsn,
    "keypoints": keypoints,
    "summary": summary,
}

# Warmer than the judge's 0.0: study material should vary between runs, and a regeneration
# at temperature 0 would return almost exactly the attempt that was just rejected.
DEFAULT_TEMPERATURE = 0.7
DEFAULT_MAX_TOKENS = 1024


class ResourceGenerator:
    """Generates one kind of study resource at a time, optionally revising after a critique."""

    def __init__(self, model_path: str = None, n_ctx: int = 4096,
                 temperature: float = DEFAULT_TEMPERATURE):
        self.client = LocalInferenceClient(model_path or GENERATOR_MODEL_PATH, n_ctx=n_ctx)
        self.temperature = temperature

    def generate(self, task: str, source: str, count: int = 5, critique: str = None,
                 previous=None, max_tokens: int = DEFAULT_MAX_TOKENS):
        """
        Produce one resource from `source`.

        task      -- one of TASKS
        count     -- how many items to produce (ignored by "summary")
        critique  -- the evaluator's regeneration_instruction from a rejected attempt
        previous  -- that rejected attempt, so the model can see what it is fixing

        Returns parsed content: a list of dicts for mcq / practice_qsn, a list of strings
        for keypoints, a string for summary. Raises ValueError when the reply cannot be
        parsed, so the caller counts it as a failed attempt instead of shipping a
        placeholder downstream.
        """
        module = TASKS.get(task)
        if module is None:
            raise ValueError(f"Unknown task {task!r}; expected one of {sorted(TASKS)}")

        user_prompt = module.build_prompt(source, count)
        if critique:
            user_prompt += _revision_block(critique, previous, module)

        messages = [
            {"role": "system", "content": module.SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]

        raw = self._complete(messages, max_tokens, module.SCHEMA)
        return module.unwrap(_parse_json(raw))

    def _complete(self, messages, max_tokens, schema):
        """Grammar-constrained call, falling back to plain decoding on older llama-cpp builds."""
        try:
            response = self.client.chat_completion(
                messages=messages, max_tokens=max_tokens,
                temperature=self.temperature, schema=schema)
        except Exception:
            response = self.client.chat_completion(
                messages=messages, max_tokens=max_tokens, temperature=self.temperature)
        return response.choices[0].message.content


def _revision_block(critique: str, previous, module) -> str:
    """
    Append the evaluator's instruction to the prompt.

    The rejected attempt is included so the model revises rather than starting over -- given
    only the instruction it tends to discard the good items along with the bad one.
    """
    block = ("\n\n[REVISION REQUIRED] An evaluator rejected your previous attempt.\n"
             f"Required fix: {critique}\n")
    if previous is not None:
        block += f'Your previous attempt:\n"""\n{module.render(previous)[:2000]}\n"""\n'
    block += ("Produce the whole resource again with that fix applied, keeping everything "
              "the evaluator did not object to. Do not mention this instruction.")
    return block


def _parse_json(raw: str):
    """Parse the model's reply, tolerating code fences or stray prose around the JSON."""
    try:
        return json.loads(raw)
    except (ValueError, TypeError):
        pass

    match = re.search(r"[\[{].*[\]}]", raw or "", re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except ValueError:
            pass

    raise ValueError(f"Could not parse generator output: {(raw or '').strip()[:200]}")


def render(task: str, content) -> str:
    """Flatten generated content into the plain text the evaluator grades."""
    module = TASKS.get(task)
    if module is None:
        return str(content)
    return module.render(content)
