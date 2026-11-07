"""The shapes a hook declaration and a hook call are made of.

`HookEvent`, `HookType` and `MatcherOperator` name the vocabulary; `HookConfig`
and its three kinds say what a source declared, and `MatcherConfig` which calls
it applies to; `HookContext` and `HookResult` are what a hook is handed and what
it answers with. Nothing here runs a hook or reads a file — this package is the
contract the rest of `hook/` is written against, and it imports nothing from it.
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

__all__ = [
    "HookEvent",
    "HookType",
    "MatcherOperator",
    "HookContext",
    "HookResult",
    "HookCallable",
    "HookConfig",
    "MatcherConfig",
    "CommandHookConfig",
    "PromptHookConfig",
    "AgentHookConfig",
]
