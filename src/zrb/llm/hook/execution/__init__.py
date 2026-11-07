"""Making a hook declaration into a running hook, and running it safely.

`create_command_hook` and `create_prompt_hook` build the callable a config
describes; `evaluate_matchers` decides whether it applies to this call;
`ThreadPoolHookExecutor` runs it on a worker thread with a timeout and
cancellation. The subprocess mechanics those need live beside them — `process_io`
feeds stdin and drains the pipes, `process_kill` takes the process group down —
and are imported from their own modules rather than re-exported here.
"""

from zrb.llm.hook.execution.creator import create_command_hook, create_prompt_hook
from zrb.llm.hook.execution.executor import (
    HookExecutionResult,
    ThreadPoolHookExecutor,
    get_hook_executor,
    shutdown_hook_executor,
)
from zrb.llm.hook.execution.matcher import evaluate_matchers

__all__ = [
    "create_command_hook",
    "create_prompt_hook",
    "evaluate_matchers",
    "HookExecutionResult",
    "ThreadPoolHookExecutor",
    "get_hook_executor",
    "shutdown_hook_executor",
]
