# Pilot corpus disclosure — one conversation for a mentor

Three caveats, one root constraint: **21 documents is a pilot corpus, not a production
statute library.** Present them together rather than as three separate surprises.

Candidate this note refers to: `qwen25-lora-20260815-090709` on `lm-legal-v0.1`.
Registry: **failed both gates.** Do not promote. The numbers below are still the right
ones to disclose.

---

## 1. Tier A / B provenance

The target manifest is **13 Tier A / 19 Tier B**. Core codes (Penal Code, Criminal
Procedure, Evidence, Civil Procedure consolidations) often have no official English PDF
on `documents.gov.lk` — pre-archive ordinances, Sinhala-only downloads, or a 404 acts
index. Those were taken from CommonLII / LankaLaw / SriLankaLaw and tagged Tier B.

What we did: every filename in `raw_pdfs/` is mapped to a manifest row; Stage 1 subjects
come from that column, not from filename guessing. Two scanned files were not OCR'd;
text-layer replacements exist but were **not** mixed into `lm-legal-v0.1`.

What we did not do: a lawyer did not audit every Tier B transcription against a
Government Printer original. Licensing of commercial consolidations is still an open
question for anything beyond a student project.

`documents.gov.lk` `/view/act/...` URLs recorded earlier now 404 (site rebuilt). Local
files we already parsed stay valid; those URLs are not re-fetchable.

---

## 2. Chapter-split leakage and the renamed metric (GI-002)

Whole-document splitting left `family_law` and `property_land` with **zero training
pairs**. Chapter-group splitting (`doc_id` + chapter) put every subject in train, val,
and test, at the cost that chapters of one statute can appear in both train and test.

So we named the metrics instead of pretending they are the same:

| Name | File | What it measures |
|------|------|------------------|
| `in_corpus_accuracy (chapter-held-out)` | `test.jsonl` | Chapters of statutes the model partly saw |
| `accuracy (document-held-out)` | `test_strict.jsonl` | A whole statute never seen at any granularity |

The 0.70 bar was written for the second. First live eval: chapter **0.717**, strict
**0.836**. Strict was *higher*, so leakage is not the reason the in-corpus number
cleared 0.70.

---

## 3. Single-document subjects — no true generalisation test

Until a second source document exists, these subjects can only be measured
in-corpus: `administrative_public`, `company_commercial`, `criminal_law`, `evidence`,
`intellectual_property`, `property_land`.

`family_law` has two documents but still no strict holdout: holding one out would
leave a single unit that cannot cover train/val/test.

`test_strict.jsonl` only covers four subjects (civil_procedure, constitutional_law,
contract_law, criminal_procedure). A pass there is not a pass on Penal Code or Evidence
as unseen documents.

---

## How this candidate actually failed the gate

Accuracy cleared 0.70 on both splits. **Do not promote.** Registry still `passed=False`.

| | chapter `test` | strict `test_strict` | after `validate_pairs` rescore |
|--|--|--|--|
| Accuracy (token-F1) | 0.717 | 0.836 | unchanged (LLM-as-judge not run — rotate the leaked key first) |
| Groundedness | 0.498 → **0.877** | 0.586 → **0.921** | now clears 0.85; original FAIL was an eval heuristic bug |
| Hallucination | 0.502 → **0.123** | 0.414 → **0.079** | now clears 0.15 |
| Latency p95 | 16.4 s | 14.9 s | still fails 8 s; Colab T4 sequential 4-bit, not serving hardware |
| vs gpt-4o-mini acc | 0.717 vs 0.871 | 0.836 vs 0.918 | still loses; slack 0.05 is not enough |

Remaining real fails: **latency on eval hardware** and **does not beat the API fallback**.
A second training run will not fix either. Keep the API as primary; treat the adapter
as a domain option. LLM-as-judge accuracy is wired in `evaluate_candidate.ipynb`
(`use_llm_judge`) and `rescore_eval.py --llm-judge` but must wait for key rotation.
