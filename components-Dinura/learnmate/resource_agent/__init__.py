"""The resource-generation agent: MCQs, practice questions, key points and summaries."""

from .graph import build_resource_graph, generate_resource, get_resource_graph
from .tasks import TASK_NAMES, TASKS, Task, get_task, render

__all__ = [
    "TASKS",
    "TASK_NAMES",
    "Task",
    "build_resource_graph",
    "generate_resource",
    "get_resource_graph",
    "get_task",
    "render",
]
