"""Delegation API — sub-agent manager and live-session registry, at L0.

Tools call into this module instead of importing ``zrb.llm.subagent.*``.
The subagent package registers its concrete implementations here at import
time. This keeps layer-1 tools from importing layer-3 orchestration.
"""

from __future__ import annotations

from typing import Protocol

from zrb.llm.any_agent_runner import AnyAgent as Agent
from zrb.llm.any_live_session_registry import AnyLiveSessionRegistry
from zrb.llm.any_live_sub_agent_session import AnyLiveSubAgentSession
from zrb.llm.any_sub_agent_definition import AnySubAgentDefinition
from zrb.llm.any_sub_agent_manager import AnySubAgentManager as SubAgentManagerAPI

LiveSessionRegistryAPI = AnyLiveSessionRegistry
LiveSubAgentSessionLike = AnyLiveSubAgentSession


_manager: SubAgentManagerAPI | None = None
_live_registry: LiveSessionRegistryAPI | None = None
_start_titling: callable | None = None  # type: ignore[assignment]


def register_subagent_manager(manager: SubAgentManagerAPI) -> None:
    global _manager
    _manager = manager


def default_sub_agent_manager() -> SubAgentManagerAPI:
    if _manager is None:
        raise RuntimeError(
            "[SYSTEM SUGGESTION] Sub-agent manager is not registered; import "
            "`zrb.llm.subagent.manager` before calling a delegation tool."
        )
    return _manager


def register_live_session_registry(registry: LiveSessionRegistryAPI) -> None:
    global _live_registry
    _live_registry = registry


def get_live_session_registry() -> LiveSessionRegistryAPI:
    if _live_registry is None:
        raise RuntimeError(
            "[SYSTEM SUGGESTION] Live sub-agent session registry is not registered; "
            "import `zrb.llm.subagent.live_session`."
        )
    return _live_registry


def register_start_titling(func) -> None:  # object-typed callable
    global _start_titling
    _start_titling = func


def start_titling(entry: object, text: str) -> None:
    """Start background titling for a live session, or no-op when unregistered."""
    fn = _start_titling
    if callable(fn):
        fn(entry, text)  # type: ignore[misc]
