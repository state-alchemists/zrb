"""Declared lifecycle hooks: the contract, the runner, and the manager.

The package's parts live in four packages of their own — `contracts` (what a
hook declaration and a call are made of), `execution` (building a hook and
running it safely), `builtin` (the two hooks zrb ships) and `manager` (where
hooks come from, which one applies, and the stop rules). `registry`,
`hook_loader`, `skill_frontmatter` and `turn_evidence` stay single modules here,
because each is one job with no parts. The names below are the surface
`zrb.llm.hook` has always had.
"""

from zrb.llm.hook.contracts.interface import HookCallable, HookContext, HookResult
from zrb.llm.hook.contracts.schema import (
    AgentHookConfig,
    CommandHookConfig,
    HookConfig,
    MatcherConfig,
    PromptHookConfig,
)
from zrb.llm.hook.contracts.types import HookEvent, HookType, MatcherOperator
from zrb.llm.hook.execution.executor import (
    HookExecutionResult,
    ThreadPoolHookExecutor,
    get_hook_executor,
    shutdown_hook_executor,
)
from zrb.llm.hook.manager.manager import HookManager, hook_manager
from zrb.llm.hook.registry import HookRegistry, hook_registry

__all__ = [
    "HookEvent",
    "HookType",
    "MatcherOperator",
    "HookContext",
    "HookResult",
    "HookExecutionResult",
    "HookCallable",
    "HookConfig",
    "MatcherConfig",
    "CommandHookConfig",
    "PromptHookConfig",
    "AgentHookConfig",
    "HookManager",
    "hook_manager",
    "HookRegistry",
    "hook_registry",
    "ThreadPoolHookExecutor",
    "get_hook_executor",
    "shutdown_hook_executor",
]
