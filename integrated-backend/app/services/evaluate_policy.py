"""
Whether a request may skip the judge.

F-01: `evaluate` on the wire is not a student-facing quality switch. The judge is
policy. Lab and component tests set LEARNMATE_ALLOW_CLIENT_EVALUATE=1.
"""

from learnmate import config as engine_config


def resolve_evaluate(client_value=None) -> bool:
    """Return the evaluate flag the worker is allowed to honour."""
    if engine_config.ALLOW_CLIENT_EVALUATE:
        return True if client_value is None else bool(client_value)
    return True
