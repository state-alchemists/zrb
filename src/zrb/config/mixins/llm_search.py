"""LLM discovery/search: plugin/skill/agent dirs, project & home search toggles, config dir names."""

from __future__ import annotations

import os

from zrb.config.helper import get_env
from zrb.util.string.conversion import to_boolean


class LLMSearchMixin:
    def __init__(self):
        self.DEFAULT_LLM_SEARCH_PROJECT: str = "on"
        self.DEFAULT_LLM_SEARCH_HOME: str = "on"
        self.DEFAULT_LLM_CONFIG_DIR_NAMES: str = ""  # Computed dynamically
        self.DEFAULT_LLM_BASE_SEARCH_DIRS: str = ""
        self.DEFAULT_LLM_EXTRA_SKILL_DIRS: str = ""
        self.DEFAULT_LLM_EXTRA_AGENT_DIRS: str = ""
        self.DEFAULT_LLM_PLUGIN_DIRS: str = ""
        super().__init__()

    @property
    def LLM_PLUGIN_DIRS(self) -> list[str]:
        plugin_dir_str = get_env(
            "LLM_PLUGIN_DIRS", self.DEFAULT_LLM_PLUGIN_DIRS, self.ENV_PREFIX
        )
        if plugin_dir_str != "":
            return [
                path.strip() for path in plugin_dir_str.split(":") if path.strip() != ""
            ]
        return []

    @LLM_PLUGIN_DIRS.setter
    def LLM_PLUGIN_DIRS(self, value: list[str]):
        os.environ[f"{self.ENV_PREFIX}_LLM_PLUGIN_DIRS"] = ":".join(value)

    @property
    def LLM_SEARCH_PROJECT(self) -> bool:
        """Enable/disable project directory search (traversal from filesystem root to cwd)."""
        return to_boolean(
            get_env(
                "LLM_SEARCH_PROJECT",
                self.DEFAULT_LLM_SEARCH_PROJECT,
                self.ENV_PREFIX,
            )
        )

    @LLM_SEARCH_PROJECT.setter
    def LLM_SEARCH_PROJECT(self, value: bool):
        os.environ[f"{self.ENV_PREFIX}_LLM_SEARCH_PROJECT"] = "on" if value else "off"

    @property
    def LLM_SEARCH_HOME(self) -> bool:
        """Enable/disable home directory search (~/.claude/, ~/.zrb/)."""
        return to_boolean(
            get_env(
                "LLM_SEARCH_HOME",
                self.DEFAULT_LLM_SEARCH_HOME,
                self.ENV_PREFIX,
            )
        )

    @LLM_SEARCH_HOME.setter
    def LLM_SEARCH_HOME(self, value: bool):
        os.environ[f"{self.ENV_PREFIX}_LLM_SEARCH_HOME"] = "on" if value else "off"

    @property
    def LLM_CONFIG_DIR_NAMES(self) -> list[str]:
        """Config subdirectory names to look for in each traversed dir (colon-separated). Default: ['.claude', '.{ROOT_GROUP_NAME}']."""
        default_names = f".claude:.{self.ROOT_GROUP_NAME}"
        names_str = get_env(
            "LLM_CONFIG_DIR_NAMES",
            (
                self.DEFAULT_LLM_CONFIG_DIR_NAMES
                if self.DEFAULT_LLM_CONFIG_DIR_NAMES
                else default_names
            ),
            self.ENV_PREFIX,
        )
        if names_str == "":
            names_str = default_names
        return [p.strip() for p in names_str.split(":") if p.strip()]

    @LLM_CONFIG_DIR_NAMES.setter
    def LLM_CONFIG_DIR_NAMES(self, value: list[str]):
        os.environ[f"{self.ENV_PREFIX}_LLM_CONFIG_DIR_NAMES"] = ":".join(value)

    @property
    def LLM_BASE_SEARCH_DIRS(self) -> list[str]:
        """Explicit base directories containing skills/, agents/, plugins/ subdirs (colon-separated)."""
        dirs_str = get_env(
            "LLM_BASE_SEARCH_DIRS",
            self.DEFAULT_LLM_BASE_SEARCH_DIRS,
            self.ENV_PREFIX,
        )
        if dirs_str != "":
            return [p.strip() for p in dirs_str.split(":") if p.strip()]
        return []

    @LLM_BASE_SEARCH_DIRS.setter
    def LLM_BASE_SEARCH_DIRS(self, value: list[str]):
        os.environ[f"{self.ENV_PREFIX}_LLM_BASE_SEARCH_DIRS"] = ":".join(value)

    @property
    def LLM_EXTRA_SKILL_DIRS(self) -> list[str]:
        """Additional direct skill directories (colon-separated)."""
        dirs_str = get_env(
            "LLM_EXTRA_SKILL_DIRS",
            self.DEFAULT_LLM_EXTRA_SKILL_DIRS,
            self.ENV_PREFIX,
        )
        if dirs_str != "":
            return [p.strip() for p in dirs_str.split(":") if p.strip()]
        return []

    @LLM_EXTRA_SKILL_DIRS.setter
    def LLM_EXTRA_SKILL_DIRS(self, value: list[str]):
        os.environ[f"{self.ENV_PREFIX}_LLM_EXTRA_SKILL_DIRS"] = ":".join(value)

    @property
    def LLM_EXTRA_AGENT_DIRS(self) -> list[str]:
        """Additional direct agent directories (colon-separated)."""
        dirs_str = get_env(
            "LLM_EXTRA_AGENT_DIRS",
            self.DEFAULT_LLM_EXTRA_AGENT_DIRS,
            self.ENV_PREFIX,
        )
        if dirs_str != "":
            return [p.strip() for p in dirs_str.split(":") if p.strip()]
        return []

    @LLM_EXTRA_AGENT_DIRS.setter
    def LLM_EXTRA_AGENT_DIRS(self, value: list[str]):
        os.environ[f"{self.ENV_PREFIX}_LLM_EXTRA_AGENT_DIRS"] = ":".join(value)
