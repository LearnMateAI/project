# 05 — MLOps workflow

See **`mlops_lifecycle.md`** for the full offline cycle:

**retrain → evaluate → stage → promote → monitor → rollback**

Key constraint: manual/scheduled, **outside** the live request path. The app only consumes a live model version pointer and must degrade to a general-purpose API fallback when the domain adapter is unavailable.
