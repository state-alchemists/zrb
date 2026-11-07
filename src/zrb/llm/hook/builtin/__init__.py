"""The hooks zrb ships: the memory reviewer and the self-review gate.

Both are `Stop` hooks registered while their flag is on, and both are a fresh
small model reading the turn rather than machinery inside it. `memory_reviewer`
writes what the turn taught, off the critical path; `self_review` reads the turn's
diff and can block the stop so the agent addresses what it found.
"""

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
    "create_self_review_hook",
    "register_self_review_hook",
]
