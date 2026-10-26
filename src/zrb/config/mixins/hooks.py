"""Hook config: enable toggle, hook dirs, timeout, and the LLM name twin."""

from __future__ import annotations

from zrb.config.env_field import (
    EnvField,
    comma_join,
    comma_list,
    on_off,
    path_list,
    path_list_join,
)
from zrb.util.string.conversion import to_boolean


class HooksMixin:
    ENV_PREFIX: str

    def __init__(self):
        self.DEFAULT_HOOKS_ENABLED: str = "on"
        self.DEFAULT_HOOKS_DIRS: str = ""
        self.DEFAULT_HOOKS_TIMEOUT: str = "30000"
        self.DEFAULT_HOOKS_EXIT_TIMEOUT: str = "2000"
        self.DEFAULT_LLM_HOOKS: str = ""
        self.DEFAULT_LLM_HOOKS_DISABLED: str = ""
        super().__init__()

    HOOKS_ENABLED = EnvField(
        to_boolean, serialize=on_off, doc="Enable/disable the hooks subsystem entirely."
    )

    HOOKS_DIRS = EnvField(
        path_list,
        serialize=path_list_join,
        doc="Colon-separated (semicolon on Windows) directories to scan for hook scripts.",
    )

    LLM_HOOKS_DISABLED = EnvField(
        comma_list,
        serialize=comma_join,
        doc=(
            "Comma-separated names of built-in hooks to leave unregistered, e.g. "
            "`journal-day-flush, journal-compliance-judge`. Empty keeps every "
            "built-in hook on, which is the default; `HOOKS_ENABLED=off` still "
            "disables all hooks, built-in and user alike, at once."
        ),
    )

    HOOKS_TIMEOUT = EnvField(int, doc="Timeout in milliseconds for hook execution.")

    HOOKS_EXIT_TIMEOUT = EnvField(
        int,
        doc=(
            "Milliseconds the chat TUI waits, as it exits, for hooks still "
            "running — a Stop hook Ctrl+C fired, then SessionEnd and detached "
            "hooks sharing one budget — before cancelling them. An agent "
            "hook still gets its own timeout."
        ),
    )

    LLM_HOOKS = EnvField(
        comma_list,
        serialize=comma_join,
        doc=(
            "Name allowlist for the hooks the CLI dispatches, the env twin of "
            "`hook_registry`. Empty means all registered hooks. "
            "Non-empty restricts dispatch to the named hooks. Finer edits live "
            "in zrb_init.py via `hook_registry` mutation."
        ),
    )
