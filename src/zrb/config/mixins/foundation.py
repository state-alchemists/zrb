"""Foundation config: env prefix, shell, editor, init, logging, session, version, banner."""

from __future__ import annotations

import logging
import os
from importlib import metadata as _metadata

from zrb.config.helper import (
    get_current_shell,
    get_default_diff_edit_command,
    get_env,
    get_log_level,
)
from zrb.util.string.conversion import to_boolean
from zrb.util.string.format import fstring_format

_DEFAULT_BANNER = """
                bb
   zzzzz rr rr  bb
     zz  rrr  r bbbbbb
    zz   rr     bb   bb
   zzzzz rr     bbbbbb   {VERSION} Pollux
   _ _ . .  . _ .  _ . . .
Your Automation Powerhouse
☕ Donate at: https://stalchmst.com
🐙 Submit issues/PR at: https://github.com/state-alchemists/zrb
🐤 Follow us at: https://twitter.com/zarubastalchmst
"""


class FoundationMixin:
    def __init__(self):
        self.DEFAULT_ENV_PREFIX: str = "ZRB"
        self.DEFAULT_SHELL: str = ""
        self.DEFAULT_EDITOR: str = "nano"
        self.DEFAULT_DIFF_EDIT_COMMAND_TPL: str = ""
        self.DEFAULT_INIT_MODULES: str = ""
        self.DEFAULT_ROOT_GROUP_NAME: str = "zrb"
        self.DEFAULT_ROOT_GROUP_DESCRIPTION: str = "Your Automation Powerhouse"
        self.DEFAULT_INIT_SCRIPTS: str = ""
        self.DEFAULT_INIT_FILE_NAME: str = "zrb_init.py"
        self.DEFAULT_LOGGING_LEVEL: str = "WARNING"
        self.DEFAULT_LOAD_BUILTIN: str = "on"
        self.DEFAULT_WARN_UNRECOMMENDED_COMMAND: str = "on"
        self.DEFAULT_SESSION_LOG_DIR: str = ""
        self.DEFAULT_TODO_DIR: str = ""
        self.DEFAULT_TODO_VISUAL_FILTER: str = ""
        self.DEFAULT_TODO_RETENTION: str = "2w"
        self.DEFAULT_VERSION: str = ""
        self.DEFAULT_ASCII_ART_DIR: str = ""
        self.DEFAULT_BANNER: str = _DEFAULT_BANNER
        self.DEFAULT_USE_TIKTOKEN: str = "off"
        self.DEFAULT_TIKTOKEN_ENCODING_NAME: str = "cl100k_base"
        self.DEFAULT_MCP_CONFIG_FILE: str = "mcp-config.json"
        super().__init__()

    @property
    def ENV_PREFIX(self) -> str:
        return os.getenv("_ZRB_ENV_PREFIX", self.DEFAULT_ENV_PREFIX)

    @ENV_PREFIX.setter
    def ENV_PREFIX(self, value: str):
        os.environ["_ZRB_ENV_PREFIX"] = value

    @property
    def LOGGER(self) -> logging.Logger:
        return logging.getLogger()

    @property
    def SHELL(self) -> str:
        return get_env(
            "SHELL",
            (self.DEFAULT_SHELL if self.DEFAULT_SHELL != "" else get_current_shell()),
            self.ENV_PREFIX,
        )

    @SHELL.setter
    def SHELL(self, value: str):
        os.environ[f"{self.ENV_PREFIX}_SHELL"] = value

    @property
    def EDITOR(self) -> str:
        return get_env("EDITOR", self.DEFAULT_EDITOR, self.ENV_PREFIX)

    @EDITOR.setter
    def EDITOR(self, value: str):
        os.environ[f"{self.ENV_PREFIX}_EDITOR"] = value

    @property
    def DIFF_EDIT_COMMAND_TPL(self) -> str:
        return get_env(
            "DIFF_EDIT_COMMAND",
            (
                self.DEFAULT_DIFF_EDIT_COMMAND_TPL
                if self.DEFAULT_DIFF_EDIT_COMMAND_TPL != ""
                else get_default_diff_edit_command(self.EDITOR)
            ),
            self.ENV_PREFIX,
        )

    @DIFF_EDIT_COMMAND_TPL.setter
    def DIFF_EDIT_COMMAND_TPL(self, value: str):
        os.environ[f"{self.ENV_PREFIX}_DIFF_EDIT_COMMAND"] = value

    @property
    def INIT_MODULES(self) -> list[str]:
        init_modules_str = get_env(
            "INIT_MODULES", self.DEFAULT_INIT_MODULES, self.ENV_PREFIX
        )
        if init_modules_str != "":
            return [
                module.strip()
                for module in init_modules_str.split(":")
                if module.strip() != ""
            ]
        return []

    @INIT_MODULES.setter
    def INIT_MODULES(self, value: list[str]):
        os.environ[f"{self.ENV_PREFIX}_INIT_MODULES"] = ":".join(value)

    @property
    def ROOT_GROUP_NAME(self) -> str:
        return get_env("ROOT_GROUP_NAME", self.DEFAULT_ROOT_GROUP_NAME, self.ENV_PREFIX)

    @ROOT_GROUP_NAME.setter
    def ROOT_GROUP_NAME(self, value: str):
        os.environ[f"{self.ENV_PREFIX}_ROOT_GROUP_NAME"] = value

    @property
    def ROOT_GROUP_DESCRIPTION(self) -> str:
        return get_env(
            "ROOT_GROUP_DESCRIPTION",
            self.DEFAULT_ROOT_GROUP_DESCRIPTION,
            self.ENV_PREFIX,
        )

    @ROOT_GROUP_DESCRIPTION.setter
    def ROOT_GROUP_DESCRIPTION(self, value: str):
        os.environ[f"{self.ENV_PREFIX}_ROOT_GROUP_DESCRIPTION"] = value

    @property
    def INIT_SCRIPTS(self) -> list[str]:
        init_scripts_str = get_env(
            "INIT_SCRIPTS", self.DEFAULT_INIT_SCRIPTS, self.ENV_PREFIX
        )
        if init_scripts_str != "":
            return [
                script.strip()
                for script in init_scripts_str.split(":")
                if script.strip() != ""
            ]
        return []

    @INIT_SCRIPTS.setter
    def INIT_SCRIPTS(self, value: list[str]):
        os.environ[f"{self.ENV_PREFIX}_INIT_SCRIPTS"] = ":".join(value)

    @property
    def INIT_FILE_NAME(self) -> str:
        return get_env("INIT_FILE_NAME", self.DEFAULT_INIT_FILE_NAME, self.ENV_PREFIX)

    @INIT_FILE_NAME.setter
    def INIT_FILE_NAME(self, value: str):
        os.environ[f"{self.ENV_PREFIX}_INIT_FILE_NAME"] = value

    @property
    def LOGGING_LEVEL(self) -> int:
        return get_log_level(
            get_env("LOGGING_LEVEL", self.DEFAULT_LOGGING_LEVEL, self.ENV_PREFIX)
        )

    @LOGGING_LEVEL.setter
    def LOGGING_LEVEL(self, value):
        if isinstance(value, int):
            value = logging.getLevelName(value)
        os.environ[f"{self.ENV_PREFIX}_LOGGING_LEVEL"] = str(value)

    @property
    def LOAD_BUILTIN(self) -> bool:
        return to_boolean(
            get_env("LOAD_BUILTIN", self.DEFAULT_LOAD_BUILTIN, self.ENV_PREFIX)
        )

    @LOAD_BUILTIN.setter
    def LOAD_BUILTIN(self, value: bool):
        os.environ[f"{self.ENV_PREFIX}_LOAD_BUILTIN"] = "on" if value else "off"

    @property
    def WARN_UNRECOMMENDED_COMMAND(self) -> bool:
        return to_boolean(
            get_env(
                "WARN_UNRECOMMENDED_COMMAND",
                self.DEFAULT_WARN_UNRECOMMENDED_COMMAND,
                self.ENV_PREFIX,
            )
        )

    @WARN_UNRECOMMENDED_COMMAND.setter
    def WARN_UNRECOMMENDED_COMMAND(self, value: bool):
        os.environ[f"{self.ENV_PREFIX}_WARN_UNRECOMMENDED_COMMAND"] = (
            "on" if value else "off"
        )

    @property
    def SESSION_LOG_DIR(self) -> str:
        default = self.DEFAULT_SESSION_LOG_DIR
        if default == "":
            default = os.path.expanduser(
                os.path.join("~", f".{self.ROOT_GROUP_NAME}", "session")
            )
        return get_env("SESSION_LOG_DIR", default, self.ENV_PREFIX)

    @SESSION_LOG_DIR.setter
    def SESSION_LOG_DIR(self, value: str):
        os.environ[f"{self.ENV_PREFIX}_SESSION_LOG_DIR"] = value

    @property
    def TODO_DIR(self) -> str:
        default = self.DEFAULT_TODO_DIR
        if default == "":
            default = os.path.expanduser(os.path.join("~", "todo"))
        return get_env("TODO_DIR", default, self.ENV_PREFIX)

    @TODO_DIR.setter
    def TODO_DIR(self, value: str):
        os.environ[f"{self.ENV_PREFIX}_TODO_DIR"] = value

    @property
    def TODO_VISUAL_FILTER(self) -> str:
        return get_env("TODO_FILTER", self.DEFAULT_TODO_VISUAL_FILTER, self.ENV_PREFIX)

    @TODO_VISUAL_FILTER.setter
    def TODO_VISUAL_FILTER(self, value: str):
        os.environ[f"{self.ENV_PREFIX}_TODO_FILTER"] = value

    @property
    def TODO_RETENTION(self) -> str:
        return get_env("TODO_RETENTION", self.DEFAULT_TODO_RETENTION, self.ENV_PREFIX)

    @TODO_RETENTION.setter
    def TODO_RETENTION(self, value: str):
        os.environ[f"{self.ENV_PREFIX}_TODO_RETENTION"] = value

    @property
    def VERSION(self) -> str:
        custom_version = os.getenv("_ZRB_CUSTOM_VERSION", "")
        if custom_version != "":
            return custom_version
        return (
            self.DEFAULT_VERSION
            if self.DEFAULT_VERSION != ""
            else _metadata.version("zrb")
        )

    @VERSION.setter
    def VERSION(self, value: str):
        os.environ["_ZRB_CUSTOM_VERSION"] = value

    @property
    def ASCII_ART_DIR(self) -> str:
        default = self.DEFAULT_ASCII_ART_DIR
        if default == "":
            default = os.path.join(f".{self.ROOT_GROUP_NAME}", "ascii-art")
        return get_env("ASCII_ART_DIR", default, self.ENV_PREFIX)

    @ASCII_ART_DIR.setter
    def ASCII_ART_DIR(self, value: str):
        os.environ[f"{self.ENV_PREFIX}_ASCII_ART_DIR"] = value

    @property
    def BANNER(self) -> str:
        return fstring_format(
            get_env("BANNER", self.DEFAULT_BANNER, self.ENV_PREFIX),
            {"VERSION": self.VERSION},
        )

    @BANNER.setter
    def BANNER(self, value: str):
        os.environ[f"{self.ENV_PREFIX}_BANNER"] = value

    @property
    def USE_TIKTOKEN(self) -> bool:
        return to_boolean(
            get_env("USE_TIKTOKEN", self.DEFAULT_USE_TIKTOKEN, self.ENV_PREFIX)
        )

    @USE_TIKTOKEN.setter
    def USE_TIKTOKEN(self, value: bool):
        os.environ[f"{self.ENV_PREFIX}_USE_TIKTOKEN"] = "on" if value else "off"

    @property
    def TIKTOKEN_ENCODING_NAME(self) -> str:
        return get_env(
            ["TIKTOKEN_ENCODING", "TIKTOKEN_ENCODING_NAME"],
            self.DEFAULT_TIKTOKEN_ENCODING_NAME,
            self.ENV_PREFIX,
        )

    @TIKTOKEN_ENCODING_NAME.setter
    def TIKTOKEN_ENCODING_NAME(self, value: str):
        os.environ[f"{self.ENV_PREFIX}_TIKTOKEN_ENCODING_NAME"] = value

    @property
    def MCP_CONFIG_FILE(self) -> str:
        return get_env("MCP_CONFIG_FILE", self.DEFAULT_MCP_CONFIG_FILE, self.ENV_PREFIX)

    @MCP_CONFIG_FILE.setter
    def MCP_CONFIG_FILE(self, value: str):
        os.environ[f"{self.ENV_PREFIX}_MCP_CONFIG_FILE"] = value
