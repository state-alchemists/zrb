"""The hook manager: where hooks come from, which one applies, and running it.

`HookManager` loads the hook sources on first use, picks and orders the hooks an
event applies to, runs them and applies the stop rules; `hook_manager` is the
process-wide instance every caller shares, and `get_run_hook_manager` returns the
run's own manager when a task bound one. `HookManagerLoading` is the half that
parses the three source formats — Claude-nested, zrb-flat and `.hook.py` — into
`HookConfig`, and `loading` is where that parsing lives.
"""

from zrb.llm.hook.manager.loading import HookManagerLoading
from zrb.llm.hook.manager.manager import HookManager, get_run_hook_manager, hook_manager

__all__ = [
    "HookManager",
    "HookManagerLoading",
    "hook_manager",
    "get_run_hook_manager",
]
