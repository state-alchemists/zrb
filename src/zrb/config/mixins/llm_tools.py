"""LLM tool config: the env twin of ``tool_registry``, and where tools write."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from zrb.config.env_field import EnvField, comma_join, comma_list


class LLMToolsMixin:
    if TYPE_CHECKING:
        # Attributes supplied by sibling mixins on the composed Config class.
        ROOT_GROUP_NAME: str  # FoundationMixin

    def __init__(self):
        self.DEFAULT_LLM_TOOLS: str = ""
        self.DEFAULT_LLM_WORKTREE_DIR: str = ""
        super().__init__()

    LLM_TOOLS = EnvField(
        comma_list,
        serialize=comma_join,
        doc=(
            "Name allowlist for the tools the agents may call, the env twin of "
            "`tool_registry`. Empty means all built-in tools. Set it "
            "to a comma-separated list of registered tool names (e.g. "
            "'Shell,Read,Write,Grep') to expose only those. Finer edits live in "
            "zrb_init.py via `tool_registry.append_tool` / `remove_tool`."
        ),
    )

    LLM_WORKTREE_DIR = EnvField(
        str,
        default_factory=lambda cfg: (
            cfg.DEFAULT_LLM_WORKTREE_DIR
            if cfg.DEFAULT_LLM_WORKTREE_DIR
            else os.path.expanduser(os.path.join("~", f".{cfg.ROOT_GROUP_NAME}", "wt"))
        ),
        doc=(
            "Directory holding the linked git worktrees EnterWorktree creates. "
            "Each repository gets its own `<repo>-<digest>` subdirectory inside "
            "this one, so two checkouts that share a name never share a path. "
            "A relative path is resolved against the starting directory. "
            "Default: ~/.zrb/wt. A sandboxed session with an explicit "
            "LLM_SANDBOX_WRITABLE_PATHS must list this directory there; the "
            "automatic (empty) list already includes it."
        ),
    )
