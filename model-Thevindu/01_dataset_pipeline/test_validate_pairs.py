"""Check the validator against cases hand-classified during review."""
import json

from validate_pairs import check_pair, unsupported_citations

rows = {r["chunk_id"] + "|" + r["pair_type"]: r
        for r in (json.loads(l) for l in open("processed_real/pairs_sample20.jsonl", encoding="utf-8"))}

# (key, should_fail, why)
CASES = [
    ("DOC-010-evidence-ordinance-consolidated-2024-C0005|summary", True,
     "excerpt has NO section number; answer says 'Section 2' from the subsection marker"),
    ("DOC-010-evidence-ordinance-consolidated-2024-C0043|summary", True,
     "cites 123/124/125; excerpt only spans 120 and 126"),
    # Not the validator's job: 153C/153D really are in this excerpt, because the excerpt
    # is a table of contents listing them. The citation is literally supported while the
    # answer is still ungrounded, so this case is handled upstream by the Stage 1 TOC
    # filter, which drops the chunk before it ever reaches Stage 2.
    ("DOC-008-constitution-C0004|qa", False,
     "TOC chunk - citation is literally present, so the TOC filter must catch it upstream"),
    ("DOC-001-19th-amendment-act-C0031|qa", False,
     "cites 153A and the excerpt literally says 'Articles 153A, 153B'"),
    ("DOC-013-maintenance-act-no-37-of-1999|summary", False,
     "cites section 5; excerpt reads 'Enforcement of 5. (1)'"),
    ("DOC-005-code-of-criminal-procedure-C0112|summary", False,
     "cites 147/148/149; all three open their own lines in the excerpt"),
]

passed = failed = 0
for key, should_fail, why in CASES:
    match = next((v for k, v in rows.items() if k.startswith(key.split("|")[0])
                  and k.endswith(key.split("|")[1])), None)
    if match is None:
        print(f"SKIP (not in sample): {key}")
        continue
    allow = {match["section_id"]} if match.get("section_id") else None
    ok, reason = check_pair(match, allow=allow)
    did_fail = not ok
    verdict = "PASS" if did_fail == should_fail else "MISMATCH"
    if verdict == "PASS":
        passed += 1
    else:
        failed += 1
    print(f"[{verdict}] expect_fail={should_fail} got_fail={did_fail}")
    print(f"         {why}")
    if did_fail:
        print(f"         reason: {reason}")
    else:
        print(f"         unsupported: {unsupported_citations(match, allow)}")

print(f"\n{passed} correct, {failed} mismatched")
