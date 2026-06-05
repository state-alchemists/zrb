"""LLM discovery/search: plugin/skill/agent dirs, project & home search toggles,
config dir names, and LSP server preference."""

from __future__ import annotations

from zrb.config.env_field import (
    EnvField,
    colon_join,
    colon_list,
    comma_join,
    comma_list,
    expanduser_colon_list,
    on_off,
)
from zrb.util.string.conversion import to_boolean


class LLMSearchMixin:
    ENV_PREFIX: str
    ROOT_GROUP_NAME: str

    def __init__(self):
        self.DEFAULT_LLM_SEARCH_PROJECT: str = "on"
        self.DEFAULT_LLM_SEARCH_HOME: str = "on"
        self.DEFAULT_LLM_CONFIG_DIR_NAMES: str = ""  # Computed dynamically
        self.DEFAULT_LLM_BASE_SEARCH_DIRS: str = ""
        self.DEFAULT_LLM_EXTRA_SKILL_DIRS: str = ""
        self.DEFAULT_LLM_EXTRA_AGENT_DIRS: str = ""
        self.DEFAULT_LLM_PLUGIN_DIRS: str = ""
        self.DEFAULT_LLM_LSP_PREFERRED_SERVERS: str = ""
        super().__init__()

    LLM_PLUGIN_DIRS = EnvField(expanduser_colon_list, serialize=colon_join)

    LLM_LSP_PREFERRED_SERVERS = EnvField(
        comma_list,
        serialize=comma_join,
        doc=(
            "Ordered, comma-separated LSP server names the agent prefers when "
            "multiple installed servers match a file (e.g. 'pyright,gopls'). The "
            "manager tries these first; names that don't match a given file are "
            "skipped. Empty (default) = use installation/registry order."
        ),
    )

    LLM_SEARCH_PROJECT = EnvField(
        to_boolean,
        serialize=on_off,
        doc=(
            "Enable/disable project directory search (traversal from filesystem "
            "root to cwd)."
        ),
    )

    LLM_SEARCH_HOME = EnvField(
        to_boolean,
        serialize=on_off,
        doc="Enable/disable home directory search (~/.claude/, ~/.zrb/).",
    )

    LLM_CONFIG_DIR_NAMES = EnvField(
        colon_list,
        serialize=colon_join,
        default_factory=lambda cfg: (
            cfg.DEFAULT_LLM_CONFIG_DIR_NAMES or f".claude:.{cfg.ROOT_GROUP_NAME}"
        ),
        doc=(
            "Config subdirectory names to look for in each traversed dir "
            "(colon-separated). Default: ['.claude', '.{ROOT_GROUP_NAME}']."
        ),
    )

    LLM_BASE_SEARCH_DIRS = EnvField(
        colon_list,
        serialize=colon_join,
        doc=(
            "Explicit base directories containing skills/, agents/, plugins/ "
            "subdirs (colon-separated)."
        ),
    )

    LLM_EXTRA_SKILL_DIRS = EnvField(
        colon_list,
        serialize=colon_join,
        doc="Additional direct skill directories (colon-separated).",
    )

    LLM_EXTRA_AGENT_DIRS = EnvField(
        colon_list,
        serialize=colon_join,
        doc="Additional direct agent directories (colon-separated).",
    )
