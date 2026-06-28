"""LLM UI slash-command aliases (15 command-list properties).

Each property reads a comma-separated env value and returns a parsed list.
Setters serialize back to comma-separated form.
"""

from __future__ import annotations

from zrb.config.env_field import EnvField, comma_join, comma_list


class LLMUICommandsMixin:
    ENV_PREFIX: str

    def __init__(self):
        self.DEFAULT_LLM_UI_COMMAND_SUMMARIZE: str = "/compress, /compact"
        self.DEFAULT_LLM_UI_COMMAND_ATTACH: str = "/attach"
        self.DEFAULT_LLM_UI_COMMAND_EXIT: str = "/q, /bye, /quit, /exit"
        self.DEFAULT_LLM_UI_COMMAND_INFO: str = "/info, /help"
        self.DEFAULT_LLM_UI_COMMAND_SAVE: str = "/save"
        self.DEFAULT_LLM_UI_COMMAND_LOAD: str = "/load"
        self.DEFAULT_LLM_UI_COMMAND_REWIND: str = "/rewind"
        self.DEFAULT_LLM_UI_COMMAND_YOLO_TOGGLE: str = "/yolo"
        self.DEFAULT_LLM_UI_COMMAND_REDIRECT_OUTPUT: str = ">, /redirect"
        self.DEFAULT_LLM_UI_COMMAND_EXEC: str = "!, /exec"
        self.DEFAULT_LLM_UI_COMMAND_SET_MODEL: str = "/model"
        self.DEFAULT_LLM_UI_COMMAND_BTW: str = "/btw"
        self.DEFAULT_LLM_UI_COMMAND_PLAN_TOGGLE: str = "/plan"
        self.DEFAULT_LLM_UI_COMMAND_COPY: str = "/copy"
        self.DEFAULT_LLM_UI_COMMAND_VOICE: str = "/voice"
        super().__init__()

    LLM_UI_COMMAND_SUMMARIZE = EnvField(
        comma_list,
        serialize=comma_join,
        doc="Comma-separated command aliases to compress/summarize the conversation context.",
    )

    LLM_UI_COMMAND_ATTACH = EnvField(
        comma_list,
        serialize=comma_join,
        doc="Comma-separated command aliases to attach a file to the conversation.",
    )

    LLM_UI_COMMAND_EXIT = EnvField(
        comma_list,
        serialize=comma_join,
        doc="Comma-separated command aliases to exit the LLM UI.",
    )

    LLM_UI_COMMAND_INFO = EnvField(
        comma_list,
        serialize=comma_join,
        doc="Comma-separated command aliases to display help and session info.",
    )

    LLM_UI_COMMAND_SAVE = EnvField(
        comma_list,
        serialize=comma_join,
        doc="Comma-separated command aliases to save the current conversation.",
    )

    LLM_UI_COMMAND_LOAD = EnvField(
        comma_list,
        serialize=comma_join,
        doc="Comma-separated command aliases to load a saved conversation.",
    )

    LLM_UI_COMMAND_REWIND = EnvField(
        comma_list,
        serialize=comma_join,
        doc="Comma-separated command aliases to rewind to a previous turn.",
    )

    LLM_UI_COMMAND_YOLO_TOGGLE = EnvField(
        comma_list,
        serialize=comma_join,
        doc="Comma-separated command aliases to toggle YOLO (auto-approve all tools) mode.",
    )

    LLM_UI_COMMAND_REDIRECT_OUTPUT = EnvField(
        comma_list,
        serialize=comma_join,
        doc="Comma-separated command aliases to redirect the next response to a file.",
    )

    LLM_UI_COMMAND_EXEC = EnvField(
        comma_list,
        serialize=comma_join,
        doc="Comma-separated command aliases to run a shell command from within the UI.",
    )

    LLM_UI_COMMAND_SET_MODEL = EnvField(
        comma_list,
        serialize=comma_join,
        doc="Comma-separated command aliases to switch the active LLM model.",
    )

    LLM_UI_COMMAND_BTW = EnvField(
        comma_list,
        serialize=comma_join,
        doc="Comma-separated command aliases to send a side-channel (non-history) message.",
    )

    LLM_UI_COMMAND_PLAN_TOGGLE = EnvField(
        comma_list,
        serialize=comma_join,
        doc="Comma-separated command aliases to toggle plan mode.",
    )

    LLM_UI_COMMAND_COPY = EnvField(
        comma_list,
        serialize=comma_join,
        doc="Comma-separated command aliases to copy the last assistant response to the clipboard.",
    )

    LLM_UI_COMMAND_VOICE = EnvField(
        comma_list,
        serialize=comma_join,
        doc="Comma-separated command aliases to toggle voice dictation mode.",
    )
