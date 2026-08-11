"""Logging and the revision block, shared by the nodes."""

from typing import Any

from .state import ResourceState
from .task import Task


def _log(state: ResourceState, message: str) -> None:
    """
    Report progress: to stdout for a CLI, and to `on_progress` when one is set.

    The API runs these graphs on a job queue where nobody is watching stdout, so the same
    messages are forwarded to a callback that writes them onto the job record. The
    callback is never allowed to break the run -- a failed progress update is a cosmetic
    problem, and a generation that dies because of one is not.
    """
    if state.get("verbose", True):
        print(message)

    report = state.get("on_progress")
    if report:
        try:
            report(message)
        except Exception:
            pass


def revision_block(task: Task, critique: str, previous: Any) -> str:
    """
    Append the rejecting gate's instruction to the next prompt.

    The rejected attempt is included so the model *revises* rather than starting over:
    given only the instruction it tends to discard the good items along with the bad one.
    Truncated at 2000 chars so a long resource cannot crowd the source passage out of the
    context window on the retry.
    """
    block = ("\n\n[REVISION REQUIRED] An evaluator rejected your previous attempt.\n"
             f"Required fix: {critique}\n")
    if previous is not None:
        block += f'Your previous attempt:\n"""\n{task.render(previous)[:2000]}\n"""\n'
    block += ("Produce the whole resource again with that fix applied, keeping everything "
              "the evaluator did not object to. Do not mention this instruction.")
    return block
