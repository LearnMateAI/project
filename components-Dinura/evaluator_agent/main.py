# full evaluator agent code is here
"""
Evaluator agent entry point.

Scores content produced by the resource-gen / chat agents from 1-100 and, when the score
falls below the threshold, emits a regeneration instruction for the generator model.

Usage:
    python main.py --download-only                       # fetch the model, then exit
    python main.py                                       # interactive
    python main.py --task summary --generated-file s.txt --source-file src.txt
    echo "..." | python main.py --task keypoints --source-file src.txt --json

In one-shot mode the exit code is 0 when the content passes the threshold and 1 when it
needs regeneration, so a shell caller can branch on it without parsing the output.

The per-type rubrics live in summary_evaluator.py, keypoints_evaluator.py, mcq_evaluator.py,
practice_qsn_evaluator.py and chat_msg_evaluator.py. Those are still stubs, so this file
soft-imports them: a task falls back to the generic rubric in agent.py until its module
defines one. See _load_specialist() for the contract each module should satisfy.
"""

import argparse
import importlib
import json
import os
import sys

# Resolve agent.py and the sibling evaluator modules against this folder, wherever the
# script is launched from and whether it is run directly or imported by the orchestrator.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agent import DEFAULT_THRESHOLD, EvaluatorLLM, ensure_model

# task name -> module in this folder that owns its rubric
TASK_MODULES = {
    "summary": "summary_evaluator",
    "keypoints": "keypoints_evaluator",
    "mcq": "mcq_evaluator",
    "practice_qsn": "practice_qsn_evaluator",
    "chat_msg": "chat_msg_evaluator",
}

# What `source` means per task, shown when prompting interactively.
SOURCE_LABELS = {
    "summary": "source text the summary came from",
    "keypoints": "source text the key points came from",
    "mcq": "source text the MCQ was built from",
    "practice_qsn": "practice question (and source text, if any)",
    "chat_msg": "conversation context the reply answers",
}


def _load_specialist(task: str):
    """
    Import the evaluator module for `task`, or return None while it is still a stub.

    A specialist module may expose either of:
        evaluate(llm, generated, source, threshold) -> verdict dict   (full control)
        CRITERIA: str                                                 (rubric only)
    """
    module_name = TASK_MODULES.get(task)
    if not module_name:
        return None

    try:
        module = importlib.import_module(module_name)
    except ImportError:
        return None

    if hasattr(module, "evaluate") or hasattr(module, "CRITERIA"):
        return module
    return None


def evaluate(llm: EvaluatorLLM, task: str, generated: str, source: str = None,
             threshold: int = DEFAULT_THRESHOLD) -> dict:
    """Route one evaluation to its specialist module, falling back to the generic judge."""
    specialist = _load_specialist(task)

    if specialist is not None and hasattr(specialist, "evaluate"):
        return specialist.evaluate(llm, generated, source, threshold)

    criteria = getattr(specialist, "CRITERIA", None) if specialist else None
    return llm.judge(task, generated, source=source, criteria=criteria, threshold=threshold)


def _read_text(inline: str, path: str) -> str:
    """Resolve a text argument given inline or as a file path."""
    if path:
        with open(path, "r", encoding="utf-8") as handle:
            return handle.read()
    return inline or ""


def _prompt_multiline(label: str) -> str:
    """Read a multi-line block from the terminal, terminated by a line containing END."""
    print(f"\nPaste the {label}, then a line containing only END:")
    lines = []
    while True:
        try:
            line = input()
        except EOFError:
            break
        if line.strip() == "END":
            break
        lines.append(line)
    return "\n".join(lines).strip()


def _print_verdict(verdict: dict, as_json: bool) -> None:
    if as_json:
        print(json.dumps(verdict, indent=2, ensure_ascii=False))
        return

    status = "PASS" if verdict["passed"] else "REGENERATE"
    print("\n" + "=" * 60)
    print(f"Task      : {verdict['task']}")
    print(f"Score     : {verdict['score']}/100  (threshold {verdict['threshold']})  ->  {status}")
    print(f"Reasoning : {verdict['reasoning']}")
    if not verdict["passed"]:
        print("\n--- Instruction for the generator model ---")
        print(verdict["regeneration_instruction"])
    print("=" * 60)


def run_interactive(llm: EvaluatorLLM, threshold: int, as_json: bool) -> None:
    tasks = list(TASK_MODULES)

    print("=" * 60)
    print("Evaluator Agent (Llama 3.2 3B, local CPU inference)")
    print("Type 'exit' or 'quit' to stop.")
    print("=" * 60)

    while True:
        print("\nEvaluation types:")
        for i, task in enumerate(tasks, start=1):
            pending = "" if _load_specialist(task) else "  (generic rubric - module not implemented yet)"
            print(f"  [{i}] {task}{pending}")

        choice = input("\nSelect type (number or name): ").strip()
        if choice.lower() in ("exit", "quit"):
            print("Exiting evaluator.")
            return
        if not choice:
            continue

        if choice.isdigit() and 1 <= int(choice) <= len(tasks):
            task = tasks[int(choice) - 1]
        elif choice in TASK_MODULES:
            task = choice
        else:
            print("Unknown evaluation type.")
            continue

        generated = _prompt_multiline("generated content to evaluate")
        if not generated:
            print("Nothing to evaluate.")
            continue

        source = _prompt_multiline(SOURCE_LABELS.get(task, "source material") + " (or END to skip)")

        print("\nEvaluating...")
        _print_verdict(evaluate(llm, task, generated, source or None, threshold), as_json)


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate generated learning content locally.")
    parser.add_argument("--task", choices=sorted(TASK_MODULES), help="Type of content being evaluated.")
    parser.add_argument("--generated", help="Content to evaluate, inline.")
    parser.add_argument("--generated-file", help="File holding the content to evaluate.")
    parser.add_argument("--source", help="Source material, inline.")
    parser.add_argument("--source-file", help="File holding the source material.")
    parser.add_argument("--threshold", type=int, default=DEFAULT_THRESHOLD,
                        help=f"Scores below this trigger regeneration (default {DEFAULT_THRESHOLD}).")
    parser.add_argument("--n-ctx", type=int, default=None, help="Override the context window.")
    parser.add_argument("--json", action="store_true", dest="as_json", help="Print the raw verdict JSON.")
    parser.add_argument("--download-only", action="store_true", help="Download the model and exit.")
    args = parser.parse_args()

    if args.download_only:
        print(f"[+] Model ready at: {ensure_model()}")
        return 0

    llm = EvaluatorLLM(n_ctx=args.n_ctx) if args.n_ctx else EvaluatorLLM()

    # One-shot mode: content given on the command line, in a file, or piped on stdin.
    generated = _read_text(args.generated, args.generated_file)
    if not generated and not sys.stdin.isatty():
        generated = sys.stdin.read()
    generated = generated.strip()

    if generated:
        if not args.task:
            parser.error("--task is required when content is supplied non-interactively")
        source = _read_text(args.source, args.source_file).strip()
        verdict = evaluate(llm, args.task, generated, source or None, args.threshold)
        _print_verdict(verdict, args.as_json)
        return 0 if verdict["passed"] else 1

    run_interactive(llm, args.threshold, args.as_json)
    return 0


if __name__ == "__main__":
    sys.exit(main())
