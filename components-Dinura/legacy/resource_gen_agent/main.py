"""
Resource-generation agent entry point.

Generates study material from source text. Evaluation and the regenerate loop live in
multiagent_management/resource_orchestrator.py; this script runs the generator alone, which
is what you want when tuning a prompt without paying for a judge pass on every attempt.

Usage:
    python main.py --task mcq --source-file passage.txt --count 5
    python main.py --task summary --source "Some passage text..."
    python main.py --task keypoints --source-file passage.txt --json
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agent import TASKS, ResourceGenerator, render  # noqa: E402


def _read_source(inline: str, path: str) -> str:
    if path:
        with open(path, "r", encoding="utf-8") as handle:
            return handle.read()
    return inline or ""


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate study resources from source text.")
    parser.add_argument("--task", choices=sorted(TASKS), required=True)
    parser.add_argument("--source", help="Source passage, inline.")
    parser.add_argument("--source-file", help="File holding the source passage.")
    parser.add_argument("--count", type=int, default=5,
                        help="Number of items to generate (sentence budget for summary).")
    parser.add_argument("--temperature", type=float, default=None)
    parser.add_argument("--json", action="store_true", dest="as_json",
                        help="Print raw JSON instead of formatted text.")
    args = parser.parse_args()

    source = _read_source(args.source, args.source_file).strip()
    if not source and not sys.stdin.isatty():
        source = sys.stdin.read().strip()
    if not source:
        parser.error("provide source text via --source, --source-file, or stdin")

    generator = (ResourceGenerator(temperature=args.temperature)
                 if args.temperature is not None else ResourceGenerator())

    print(f"[*] Generating {args.task} from {len(source)} chars of source...")
    try:
        content = generator.generate(args.task, source, count=args.count)
    except ValueError as exc:
        print(f"[!] {exc}")
        return 1

    if args.as_json:
        print(json.dumps(content, indent=2, ensure_ascii=False))
    else:
        print("\n" + "=" * 60)
        print(render(args.task, content))
        print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
