"""
Orchestrates the resource-generation agent and the evaluator agent.

This is the loop the evaluator was designed for: study material is generated from source
text, checked, and regenerated once with the critique attached if it falls short. Unlike a
chat reply, nobody is waiting mid-conversation for it, so the extra pass is affordable.

Two gates, cheapest first:

    generate -> structural validators -> LLM judge -> accept
                      |                      |
                      +-- fail ---> regenerate with the reason attached

Most bad generations fail mechanically (three options instead of four, a correct_answer
that appears in no option, an empty summary). Those are decided in plain Python in
microseconds, so the ~25 second judge call is only ever spent on well-formed content.

Run:  python resource_orchestrator.py
"""

import os
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
_COMPONENTS = os.path.dirname(_HERE)
CHAT_AGENT_DIR = os.path.join(_COMPONENTS, "chat-agent")
EVALUATOR_DIR = os.path.join(_COMPONENTS, "evaluator_agent")
RESOURCE_GEN_DIR = os.path.join(_COMPONENTS, "resource_gen_agent")

for _path in (_HERE, RESOURCE_GEN_DIR, EVALUATOR_DIR, CHAT_AGENT_DIR):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import validators  # noqa: E402  evaluator_agent/validators.py
from scorelog import log_evaluation  # noqa: E402
from agent import DEFAULT_THRESHOLD, EvaluatorLLM  # noqa: E402  evaluator_agent/agent.py


def _load_module(name: str, path: str):
    """
    Load a file under an explicit module name.

    evaluator_agent/agent.py and resource_gen_agent/agent.py are both called "agent", so a
    plain `import agent` returns whichever landed in sys.modules first -- silently handing
    back the evaluator where the generator was meant. Naming them apart removes the clash.
    """
    import importlib.util
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


resource_agent = _load_module("resource_gen_agent_agent",
                              os.path.join(RESOURCE_GEN_DIR, "agent.py"))

# task -> evaluator module holding that task's CRITERIA rubric
_RUBRIC_MODULES = {
    "mcq": "mcq_evaluator",
    "practice_qsn": "practice_qsn_evaluator",
    "keypoints": "keypoints_evaluator",
    "summary": "summary_evaluator",
}


def _criteria_for(task: str):
    """Load the task's rubric, or None to fall back to the generic one in agent.py."""
    module_name = _RUBRIC_MODULES.get(task)
    if not module_name:
        return None
    try:
        import importlib
        return getattr(importlib.import_module(module_name), "CRITERIA", None)
    except ImportError:
        return None


class ResourceOrchestrator:
    """Generates one study resource, regenerating once if it fails a gate."""

    MAX_ATTEMPTS = 2

    def __init__(self, threshold: int = DEFAULT_THRESHOLD, max_attempts: int = MAX_ATTEMPTS,
                 verbose: bool = True, evaluate: bool = True):
        self.threshold = threshold
        self.max_attempts = max_attempts
        self.verbose = verbose
        # Turning this off leaves generation intact and skips both gates, which is how you
        # measure what evaluation is actually costing you.
        self.evaluate = evaluate

        self._log("[*] Starting resource-gen agent...")
        self.generator = resource_agent.ResourceGenerator()

        if self.evaluate:
            self._log("[*] Starting evaluator agent...")
            self.judge = EvaluatorLLM()
        else:
            self.judge = None

    def _log(self, message: str):
        if self.verbose:
            print(message)

    def produce(self, task: str, source: str, count: int = 5) -> dict:
        """
        Generate one resource and run it through both gates.

        Returns:
            {task, attempts, content, verdict, accepted}
        where `attempts` is [{content, stage, passed, score, reasons, verdict}, ...] and
        `content` is the LAST attempt -- consistent with the chat orchestrator, the
        regenerated output is what you get, pass or fail.
        """
        attempts = []
        critique = None
        previous = None

        for attempt in range(1, self.max_attempts + 1):
            self._log(f"[*] Generating {task} (attempt {attempt}/{self.max_attempts})...")
            started = time.time()

            try:
                content = self.generator.generate(task, source, count=count,
                                                  critique=critique, previous=previous)
            except ValueError as exc:
                # Unparseable output is a failed attempt, not a crash: retry with the
                # parse failure as the critique.
                self._log(f"[!] Generation failed to parse: {exc}")
                record = {"content": None, "stage": "parse", "passed": False,
                          "score": None, "reasons": [str(exc)], "verdict": None}
                attempts.append(record)
                log_evaluation(task, attempt, None, False, self.threshold, stage="parse",
                               elapsed=time.time() - started)
                critique = "Return valid JSON in exactly the requested shape."
                previous = None
                continue

            record = self._check(task, content, source, attempt, started)
            attempts.append(record)

            if record["passed"] or attempt == self.max_attempts:
                break

            critique = record["critique"]
            previous = content
            self._log(f"[*] Feedback: {critique}")

        final = attempts[-1]
        return {
            "task": task,
            "attempts": attempts,
            "content": final["content"],
            "verdict": final["verdict"],
            "accepted": final["passed"],
        }

    def _check(self, task: str, content, source: str, attempt: int, started: float) -> dict:
        """Structural gate first; the judge only sees content that already passed it."""
        ok, reasons = validators.validate(task, content)
        if not ok:
            self._log(f"[*] Structural check FAILED: {'; '.join(reasons)}")
            log_evaluation(task, attempt, None, False, self.threshold, stage="validator",
                           elapsed=time.time() - started, extra={"reasons": reasons})
            return {
                "content": content, "stage": "validator", "passed": False, "score": None,
                "reasons": reasons, "verdict": None,
                "critique": "Fix these structural problems and change nothing else: "
                            + "; ".join(reasons),
            }

        if not self.evaluate:
            return {"content": content, "stage": "skipped", "passed": True, "score": None,
                    "reasons": [], "verdict": None, "critique": ""}

        self._log("[*] Structural check passed. Judging...")
        rendered = resource_agent.render(task, content)
        verdict = self.judge.judge(task, rendered, source=source,
                                   criteria=_criteria_for(task), threshold=self.threshold)

        log_evaluation(task, attempt, verdict["score"], verdict["passed"], self.threshold,
                       stage="judge", elapsed=time.time() - started)
        self._log(f"[*] Score {verdict['score']}/100 -> "
                  f"{'PASS' if verdict['passed'] else 'REGENERATE'}")

        return {
            "content": content, "stage": "judge", "passed": verdict["passed"],
            "score": verdict["score"], "reasons": [], "verdict": verdict,
            "critique": verdict["regeneration_instruction"],
        }
