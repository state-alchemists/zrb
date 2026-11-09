"""The hooks zrb ships: memory (reviewer, log lines, recall) and self-review.

The memory hooks write what a turn taught, record that it happened, and put a
stored claim in front of a prompt that names its subject. The reviewer and the
self-review gate are a fresh small model reading the turn rather than machinery
inside it; the log and recall hooks call no model at all.
"""

from zrb.llm.hook.builtin.memory_recall import (
    build_recall_hook_config,
    create_recall_hook,
    register_recall_hook,
)
from zrb.llm.hook.builtin.memory_reviewer import (
    build_memory_reviewer_hook_config,
    register_memory_reviewer_hook,
)
from zrb.llm.hook.builtin.self_review import (
    create_self_review_hook,
    register_self_review_hook,
)

__all__ = [
    "build_memory_reviewer_hook_config",
    "register_memory_reviewer_hook",
    "build_recall_hook_config",
    "create_recall_hook",
    "register_recall_hook",
    "create_self_review_hook",
    "register_self_review_hook",
]
