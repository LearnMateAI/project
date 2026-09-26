# LearnMate AI / security audit

This folder is the AI/security audit on branch `docs/learnmate-ai-security-audit`.

**Baseline:** `origin/main` at `156b640` (merge of PR #24 / `thevindu-feature`).
**Also read:** `origin/deployment` (`9dccafc`, 2026-09-13) and `origin/demo1`
(`a3310b3`, 2026-09-21).

The first commit on this branch was docs-only. The current branch also ships
engine/API/UI fixes for findings **F-01–F-14** plus the offline golden eval.

| Document | What it is |
| --- | --- |
| [LEARNMATE_AI_ENGINEER_AUDIT.md](./LEARNMATE_AI_ENGINEER_AUDIT.md) | Full report: architecture, A–L scorecard, cited findings, eval plan, rewritten prompts, roadmap, interview STAR stories |
| [BRANCH_BASELINE.md](./BRANCH_BASELINE.md) | What differs between `main`, `deployment`, and `demo1` so the audit stays honest about what is live |
| [EVAL_RESULTS.md](./EVAL_RESULTS.md) | Before/after numbers for F-01 / F-02 / F-03 on the 15-item golden set |
| [F_FINDINGS_STATUS.md](./F_FINDINGS_STATUS.md) | What “correct” means for F-01–F-14 and what still is not |

The audit treats repo prompts and PDFs as **data**, not as instructions to the reviewer.
