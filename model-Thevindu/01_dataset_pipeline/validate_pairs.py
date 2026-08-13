"""Reject generated pairs that cite a provision number their excerpt never contains.

Stage 2 had no automated validation, which is how a 38% ungrounded-citation rate went
undetected into a training run. Measured on the first live batch over the real corpus:
15 of 40 pairs cited at least one section number absent from the excerpt, 12 of them
summaries. Two failure modes were behind it -- chunks starting mid-provision (the model
supplied a number from memory) and table-of-contents fragments (the model answered from
pretrained knowledge entirely).

Training on those teaches the model to invent citations, which is precisely what
acceptance_thresholds.yaml gates on (groundedness >= 0.85, hallucination <= 0.15).

Used two ways:
  - imported by generate_training_pairs.py, which drops failing pairs as it writes
  - standalone audit of an existing file:
      python validate_pairs.py processed_real/pairs.jsonl
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

# A citation in the ANSWER only counts when explicitly labelled, so ordinary numbers
# ("three months", "fifty per centum") are not mistaken for provision references.
_CITE = re.compile(
    r"\b(?:section|sections|sec\.|s\.|article|articles|art\.|chapter|part|rule|order)\s+"
    r"([0-9]{1,3}[A-Za-z]{0,2})",
    re.I,
)

# In the EXCERPT the same provision may appear in four shapes. These have to be
# matched narrowly: an earlier attempt accepted any digits followed by a period, which
# in statutory prose (full of "(1)." and numeric amounts) whitelisted nearly every
# number and let real inventions through -- it scored 1/40 where hand-review found 15.
_IN_SRC = (
    # "section 91", "Article 33"
    re.compile(
        r"\b(?:section|sections|sec\.|s\.|article|articles|art\.|chapter|part|rule|order)\s+"
        r"([0-9]{1,3}[A-Za-z]{0,2})",
        re.I,
    ),
    # a provision opening its own line: "147. The officer in charge..."
    re.compile(r"(?:^|\n)\s*([0-9]{1,3}[A-Za-z]{0,2})\s*\."),
    # marginal note runs into the number: "Enforcement of 5. (1) Subject to..."
    re.compile(r"([0-9]{1,3}[A-Za-z]{0,2})\s*\.\s*\([0-9a-z]"),
    # alphanumeric provisions are unambiguous wherever they appear: "153A", "111D"
    re.compile(r"\b([0-9]{1,3}[A-Za-z]{1,2})\b"),
)


def numbers_in_excerpt(text: str) -> set[str]:
    found: set[str] = set()
    for rx in _IN_SRC:
        for m in rx.finditer(text):
            found.add(m.group(1).lower())
    return found


def unsupported_citations(pair: dict[str, Any], allow: set[str] | None = None) -> list[str]:
    """Provision numbers asserted in the answer that the excerpt does not contain.

    `allow` carries the section id Stage 1 forward-filled onto a continuation chunk:
    the excerpt genuinely belongs to it even though the number isn't restated.
    """
    answer = pair.get("output") or ""
    excerpt = pair.get("input") or ""
    cited = {m.group(1).lower() for m in _CITE.finditer(answer)}
    if not cited:
        return []
    permitted = numbers_in_excerpt(excerpt) | {a.lower() for a in (allow or set())}
    return sorted(cited - permitted)


def check_pair(pair: dict[str, Any], allow: set[str] | None = None) -> tuple[bool, str]:
    """(ok, reason). Reason is empty when the pair passes."""
    answer = (pair.get("output") or "").strip()
    if len(answer) < 40:
        return False, "answer too short"
    bad = unsupported_citations(pair, allow)
    if bad:
        return False, f"cites {','.join(bad)} not in excerpt"
    return True, ""


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 2
    path = Path(argv[1])
    rows = [json.loads(ln) for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]

    failures: list[tuple[dict[str, Any], str]] = []
    by_type: Counter[str] = Counter()
    for r in rows:
        ok, reason = check_pair(r, allow={r["section_id"]} if r.get("section_id") else None)
        if not ok:
            failures.append((r, reason))
            by_type[r.get("pair_type", "?")] += 1

    rate = len(failures) / len(rows) if rows else 0.0
    print(f"file          : {path}")
    print(f"pairs         : {len(rows)}")
    print(f"failing       : {len(failures)} ({rate:.0%})")
    print(f"by pair_type  : {dict(by_type)}")
    for r, reason in failures[:10]:
        print(f"\n[{r.get('pair_type')}] {r.get('chunk_id')}  -- {reason}")
        print("   ", (r.get("output") or "")[:160].replace("\n", " "))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
