# Last recorded pytest results

Branch: `testing` only. Command run from the repository root.

| Date | Command | Passed | Failed | Skipped | Notes |
|------|---------|--------|--------|---------|-------|
| 2026-08-19 | `python -m pytest testing/unit testing/integration testing/uat --tb=line` | **97** | 0 | **4** | Skips are live UAT (`LEARNMATE_UAT` unset). No GGUF load. |

## Layer breakdown

| Layer | Result |
|-------|--------|
| Unit (`testing/unit`) | all passed |
| Integration (`testing/integration`) | all passed |
| UAT (`testing/uat`) | 4 skipped until `LEARNMATE_UAT=1` and API `:8010` |

## How to re-run

```bash
pip install -r testing/requirements.txt
python -m pytest testing/unit testing/integration testing/uat -q
```
