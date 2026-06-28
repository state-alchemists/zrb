"""Foundation config: env prefix, shell, editor, init, logging, session, version, banner."""

from __future__ import annotations

import logging
import os
from importlib import metadata as _metadata

from zrb.config.env_field import (
    EnvField,
    colon_join,
    colon_list,
    comma_join,
    comma_or_colon_list,
    on_off,
)
from zrb.config.helper import (
    get_current_shell,
    get_default_diff_edit_command,
    get_log_level,
    is_termux,
)
from zrb.util.string.conversion import to_boolean
from zrb.util.string.format import fstring_format


def _serialize_log_level(value) -> str:
    """Mirror the old setter: accept a numeric level or a name, store a name."""
    if isinstance(value, int):
        return logging.getLevelName(value)
    return str(value)


_DEFAULT_BANNER = """
                bb
   zzzzz rr rr  bb
     zz  rrr  r bbbbbb
    zz   rr     bb   bb
   zzzzz rr     bbbbbb   {VERSION} Jinrui
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

    # Bootstrap key: reads/writes the bare _ZRB_ENV_PREFIX, so it cannot itself
    # depend on ENV_PREFIX (no_prefix avoids the recursion).
    ENV_PREFIX = EnvField(
        str,
        no_prefix=True,
        aliases=["_ZRB_ENV_PREFIX"],
        write_key="_ZRB_ENV_PREFIX",
        doc="Prefix for all Zrb env vars (used for white-labeling a custom CLI).",
    )

    @property
    def LOGGER(self) -> logging.Logger:
        return logging.getLogger()

    SHELL = EnvField(
        str,
        default_factory=lambda c: c.DEFAULT_SHELL or get_current_shell(),
        doc="Shell used by CmdTask. Auto-detected when unset.",
    )

    IS_TERMUX = EnvField(
        to_boolean,
        serialize=on_off,
        default_factory=lambda c: on_off(is_termux()),
        doc="Whether zrb runs under Termux. Auto-detected; override to force "
        "Termux-specific behavior such as Tab-to-cycle-mode keybindings.",
    )

    EDITOR = EnvField(str, doc="Default text editor for interactive prompts.")

    DIFF_EDIT_COMMAND_TPL = EnvField(
        str,
        aliases=["DIFF_EDIT_COMMAND"],
        write_key="DIFF_EDIT_COMMAND",
        default_factory=lambda c: (
            c.DEFAULT_DIFF_EDIT_COMMAND_TPL or get_default_diff_edit_command(c.EDITOR)
        ),
        doc="Template command for interactive file editing. Derived from EDITOR.",
    )

    INIT_MODULES = EnvField(
        comma_or_colon_list,
        serialize=comma_join,
        doc="Comma-separated importable module names zrb imports on startup so "
        "their task definitions register (e.g. a shared team task package). "
        "Colon-separated values are still accepted.",
    )

    ROOT_GROUP_NAME = EnvField(str, doc="Name of the root command group in help menus.")

    ROOT_GROUP_DESCRIPTION = EnvField(
        str, doc="Description for the root command group."
    )

    INIT_SCRIPTS = EnvField(
        colon_list,
        serialize=colon_join,
        doc="Colon-separated Python script paths zrb runs on startup (in addition "
        "to the discovered INIT_FILE_NAME files) to register task definitions.",
    )

    INIT_FILE_NAME = EnvField(
        str,
        doc="Name of the task-definition file zrb auto-loads. On startup zrb walks "
        "from the current directory up to the filesystem root and loads every "
        "file with this name it finds.",
    )

    LOGGING_LEVEL = EnvField(
        get_log_level,
        serialize=_serialize_log_level,
        doc=(
            "Verbosity of Zrb's internal logs, from least to most verbose:\n"
            "- 'CRITICAL'\n"
            "- 'ERROR'\n"
            "- 'WARNING'\n"
            "- 'INFO'\n"
            "- 'DEBUG'"
        ),
    )

    LOAD_BUILTIN = EnvField(
        to_boolean,
        serialize=on_off,
        doc="Whether to load pre-packaged tasks (Git, UUID, base64, etc.).",
    )

    WARN_UNRECOMMENDED_COMMAND = EnvField(
        to_boolean,
        serialize=on_off,
        doc="Show warnings for potentially unsafe shell commands.",
    )

    SESSION_LOG_DIR = EnvField(
        str,
        default_factory=lambda c: (
            c.DEFAULT_SESSION_LOG_DIR
            or os.path.expanduser(os.path.join("~", f".{c.ROOT_GROUP_NAME}", "session"))
        ),
        doc="Directory for session-specific logs and history.",
    )

    TODO_DIR = EnvField(
        str,
        default_factory=lambda c: (
            c.DEFAULT_TODO_DIR or os.path.expanduser(os.path.join("~", "todo"))
        ),
        doc="Directory for the todo.txt file.",
    )

    TODO_VISUAL_FILTER = EnvField(
        str,
        aliases=["TODO_FILTER"],
        write_key="TODO_FILTER",
        doc="Filter string applied to todo task listings.",
    )

    TODO_RETENTION = EnvField(
        str, doc="How long completed todo items are kept before archiving (e.g. 2w)."
    )

    # Internal version key: bare _ZRB_CUSTOM_VERSION, falling back to the
    # installed package version.
    VERSION = EnvField(
        str,
        no_prefix=True,
        aliases=["_ZRB_CUSTOM_VERSION"],
        write_key="_ZRB_CUSTOM_VERSION",
        default_factory=lambda c: c.DEFAULT_VERSION or _metadata.version("zrb"),
        doc="Displayed version string. Overrides the installed package version.",
    )

    ASCII_ART_DIR = EnvField(
        str,
        default_factory=lambda c: (
            c.DEFAULT_ASCII_ART_DIR
            or os.path.join(f".{c.ROOT_GROUP_NAME}", "ascii-art")
        ),
        doc="Directory for ASCII art assets.",
    )

    BANNER = EnvField(
        str,
        transform=lambda v, c: fstring_format(v, {"VERSION": c.VERSION}),
        doc="Banner shown at CLI start. Supports {VERSION} formatting.",
    )

    USE_TIKTOKEN = EnvField(
        to_boolean,
        serialize=on_off,
        doc="Whether to use tiktoken for token counting.",
    )

    TIKTOKEN_ENCODING_NAME = EnvField(
        str,
        aliases=["TIKTOKEN_ENCODING", "TIKTOKEN_ENCODING_NAME"],
        doc="Tiktoken encoding name (e.g. cl100k_base).",
    )

    MCP_CONFIG_FILE = EnvField(str, doc="Path to the MCP server config file.")
