"""Delegation tools: run an agent, hand it a message, and track its worktree."""

from zrb.llm.tool.delegate.background import (
    background_delegation_live_context,
    create_get_delegation_result_tool,
    get_background_registry,
    get_own_background_handles,
    register_background_handle,
    start_background_run,
)
from zrb.llm.tool.delegate.message import create_send_message_to_subagent_tool
from zrb.llm.tool.delegate.runner import (
    AgentTaskResult,
    BufferedUI,
    agent_not_found_message,
    agent_roster_doc,
    create_delegate_to_agent_tool,
    create_search_agent_tool,
    fire_subagent_hook,
    persist_subagent_history,
    run_agent_task,
)
from zrb.llm.tool.delegate.worktree import (
    enter_worktree,
    exit_worktree,
    list_worktrees,
)

__all__ = [
    "AgentTaskResult",
    "BufferedUI",
    "agent_not_found_message",
    "agent_roster_doc",
    "background_delegation_live_context",
    "create_delegate_to_agent_tool",
    "create_get_delegation_result_tool",
    "create_search_agent_tool",
    "create_send_message_to_subagent_tool",
    "enter_worktree",
    "exit_worktree",
    "fire_subagent_hook",
    "get_background_registry",
    "get_own_background_handles",
    "list_worktrees",
    "persist_subagent_history",
    "register_background_handle",
    "run_agent_task",
    "start_background_run",
]
