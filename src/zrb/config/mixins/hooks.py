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
        self.DEFAULT_LLM_HOOKS: str = ""
        super().__init__()

    HOOKS_ENABLED = EnvField(
        to_boolean, serialize=on_off, doc="Enable/disable the hooks subsystem entirely."
    )

    HOOKS_DIRS = EnvField(
        path_list,
        serialize=path_list_join,
        doc="Colon-separated (semicolon on Windows) directories to scan for hook scripts.",
    )

    HOOKS_TIMEOUT = EnvField(int, doc="Timeout in milliseconds for hook execution.")

    LLM_HOOKS = EnvField(
        comma_list,
        serialize=comma_join,
        doc=(
            "Name allowlist for the hooks zrb dispatches, the env twin of "
            "`hook_registry`. Empty means all registered hooks. "
            "Non-empty restricts dispatch to the named hooks. Finer edits live "
            "in zrb_init.py via `hook_registry` mutation."
        ),
    )
