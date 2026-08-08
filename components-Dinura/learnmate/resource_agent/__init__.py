"""
The resource-generation agent: MCQs, practice questions, key points and summaries.

One run is one pass through a LangGraph state machine:

    generate -> check -> decide -+-> persist -> END
        ^                        |
        +------ regenerate ------+

`check` runs two gates, cheapest first: the structural validators (plain Python,
microseconds) and then the LLM judge (~25 seconds). Most bad generations fail
mechanically, so the judge is only ever spent on content that is already well-formed.

The retry budget is 2: one generation plus one regeneration. The last attempt is returned
whether or not it passed, and `accepted` reports which -- a student waiting on a quiz is
better served by flagged output than by nothing.

Four resource types, one file each. Each owns its prompt, its JSON schema, how to read the
reply and how to render it; everything else is shared, so a fifth type is one new module
plus one line in tasks.py.

    mcq.py           multiple-choice questions     {question, options[4], correct_answer}
    practice_qsn.py  short-answer questions        {question, answer}
    keypoints.py     a list of key points          ["point", ...]
    summary.py       one block of connected prose  "..."

Where things live, in reading order:

    task.py          the Task contract every resource type implements
    mcq.py etc.      the four types
    tasks.py         the registry: TASKS, TASK_NAMES, get_task, render
    state.py         ResourceState -- what flows between nodes
    helpers.py       logging, and the revision block used on a retry
    generate.py      node 1  ask the generator, folding in a critique when retrying
    check.py         node 2  the two gates
    routing.py               the accept-or-retry branch
    persist.py       node 3  store the resource and its attempt trail
    graph.py         the LangGraph wiring
    agent.py         generate_resource() -- the public entry point

Three more modules sit on top, for asks that are about a whole PDF rather than one passage
-- neither the 6000-character passage nor the 1024-token reply is enough for those:

    whole_document.py    generate_document_items() -- groups of pages generated separately
                         and pooled, by total (count=40) or by rate (per_page=2)
    document_mcqs.py     generate_document_mcqs() -- the count-based entry point for mcq
    document_summary.py  summarize_document() -- every page summarised, then folded into
                         one comprehensive summary

The source passage comes from ingestion.build_source_text, which turns a PDF and an
optional topic into the whole pages most relevant to it.
"""

from .agent import generate_resource
# Re-exported under a qualified name: "COUNT_CHOICES" says nothing at package scope.
from .document_mcqs import COUNT_CHOICES as MCQ_COUNT_CHOICES
from .document_mcqs import DEFAULT_COUNT as MCQ_DEFAULT_COUNT
from .document_mcqs import generate_document_mcqs
from .document_summary import summarize_document
from .whole_document import DEFAULT_PER_PAGE, PER_PAGE_CHOICES, generate_document_items
from .graph import build_resource_graph, get_resource_graph
from .task import Task
from .tasks import TASK_NAMES, TASKS, get_task, render

__all__ = [
    "DEFAULT_PER_PAGE",
    "MCQ_COUNT_CHOICES",
    "MCQ_DEFAULT_COUNT",
    "PER_PAGE_CHOICES",
    "TASKS",
    "TASK_NAMES",
    "Task",
    "build_resource_graph",
    "generate_document_items",
    "generate_document_mcqs",
    "generate_resource",
    "get_resource_graph",
    "get_task",
    "render",
    "summarize_document",
]
