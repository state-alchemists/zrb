"""LLM UI slash-command aliases (12 command-list properties).

Each property reads a comma-separated env value and returns a parsed list.
Setters serialize back to comma-separated form.
"""

from __future__ import annotations

import os

from zrb.config.helper import get_env


class LLMUICommandsMixin:
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
        super().__init__()

    def _parse_command_list(self, cmd_str: str) -> list[str]:
        return [cmd.strip() for cmd in cmd_str.split(",") if cmd.strip() != ""]

    @property
    def LLM_UI_COMMAND_SUMMARIZE(self) -> list[str]:
        return self._parse_command_list(
            get_env(
                "LLM_UI_COMMAND_SUMMARIZE",
                self.DEFAULT_LLM_UI_COMMAND_SUMMARIZE,
                self.ENV_PREFIX,
            )
        )

    @LLM_UI_COMMAND_SUMMARIZE.setter
    def LLM_UI_COMMAND_SUMMARIZE(self, value: list[str]):
        os.environ[f"{self.ENV_PREFIX}_LLM_UI_COMMAND_SUMMARIZE"] = ",".join(value)

    @property
    def LLM_UI_COMMAND_ATTACH(self) -> list[str]:
        return self._parse_command_list(
            get_env(
                "LLM_UI_COMMAND_ATTACH",
                self.DEFAULT_LLM_UI_COMMAND_ATTACH,
                self.ENV_PREFIX,
            )
        )

    @LLM_UI_COMMAND_ATTACH.setter
    def LLM_UI_COMMAND_ATTACH(self, value: list[str]):
        os.environ[f"{self.ENV_PREFIX}_LLM_UI_COMMAND_ATTACH"] = ",".join(value)

    @property
    def LLM_UI_COMMAND_EXIT(self) -> list[str]:
        return self._parse_command_list(
            get_env(
                "LLM_UI_COMMAND_EXIT",
                self.DEFAULT_LLM_UI_COMMAND_EXIT,
                self.ENV_PREFIX,
            )
        )

    @LLM_UI_COMMAND_EXIT.setter
    def LLM_UI_COMMAND_EXIT(self, value: list[str]):
        os.environ[f"{self.ENV_PREFIX}_LLM_UI_COMMAND_EXIT"] = ",".join(value)

    @property
    def LLM_UI_COMMAND_INFO(self) -> list[str]:
        return self._parse_command_list(
            get_env(
                "LLM_UI_COMMAND_INFO",
                self.DEFAULT_LLM_UI_COMMAND_INFO,
                self.ENV_PREFIX,
            )
        )

    @LLM_UI_COMMAND_INFO.setter
    def LLM_UI_COMMAND_INFO(self, value: list[str]):
        os.environ[f"{self.ENV_PREFIX}_LLM_UI_COMMAND_INFO"] = ",".join(value)

    @property
    def LLM_UI_COMMAND_SAVE(self) -> list[str]:
        return self._parse_command_list(
            get_env(
                "LLM_UI_COMMAND_SAVE",
                self.DEFAULT_LLM_UI_COMMAND_SAVE,
                self.ENV_PREFIX,
            )
        )

    @LLM_UI_COMMAND_SAVE.setter
    def LLM_UI_COMMAND_SAVE(self, value: list[str]):
        os.environ[f"{self.ENV_PREFIX}_LLM_UI_COMMAND_SAVE"] = ",".join(value)

    @property
    def LLM_UI_COMMAND_LOAD(self) -> list[str]:
        return self._parse_command_list(
            get_env(
                "LLM_UI_COMMAND_LOAD",
                self.DEFAULT_LLM_UI_COMMAND_LOAD,
                self.ENV_PREFIX,
            )
        )

    @LLM_UI_COMMAND_LOAD.setter
    def LLM_UI_COMMAND_LOAD(self, value: list[str]):
        os.environ[f"{self.ENV_PREFIX}_LLM_UI_COMMAND_LOAD"] = ",".join(value)

    @property
    def LLM_UI_COMMAND_REWIND(self) -> list[str]:
        return self._parse_command_list(
            get_env(
                "LLM_UI_COMMAND_REWIND",
                self.DEFAULT_LLM_UI_COMMAND_REWIND,
                self.ENV_PREFIX,
            )
        )

    @LLM_UI_COMMAND_REWIND.setter
    def LLM_UI_COMMAND_REWIND(self, value: list[str]):
        os.environ[f"{self.ENV_PREFIX}_LLM_UI_COMMAND_REWIND"] = ",".join(value)

    @property
    def LLM_UI_COMMAND_YOLO_TOGGLE(self) -> list[str]:
        return self._parse_command_list(
            get_env(
                "LLM_UI_COMMAND_YOLO_TOGGLE",
                self.DEFAULT_LLM_UI_COMMAND_YOLO_TOGGLE,
                self.ENV_PREFIX,
            )
        )

    @LLM_UI_COMMAND_YOLO_TOGGLE.setter
    def LLM_UI_COMMAND_YOLO_TOGGLE(self, value: list[str]):
        os.environ[f"{self.ENV_PREFIX}_LLM_UI_COMMAND_YOLO_TOGGLE"] = ",".join(value)

    @property
    def LLM_UI_COMMAND_REDIRECT_OUTPUT(self) -> list[str]:
        return self._parse_command_list(
            get_env(
                "LLM_UI_COMMAND_REDIRECT_OUTPUT",
                self.DEFAULT_LLM_UI_COMMAND_REDIRECT_OUTPUT,
                self.ENV_PREFIX,
            )
        )

    @LLM_UI_COMMAND_REDIRECT_OUTPUT.setter
    def LLM_UI_COMMAND_REDIRECT_OUTPUT(self, value: list[str]):
        os.environ[f"{self.ENV_PREFIX}_LLM_UI_COMMAND_REDIRECT_OUTPUT"] = ",".join(
            value
        )

    @property
    def LLM_UI_COMMAND_EXEC(self) -> list[str]:
        return self._parse_command_list(
            get_env(
                "LLM_UI_COMMAND_EXEC",
                self.DEFAULT_LLM_UI_COMMAND_EXEC,
                self.ENV_PREFIX,
            )
        )

    @LLM_UI_COMMAND_EXEC.setter
    def LLM_UI_COMMAND_EXEC(self, value: list[str]):
        os.environ[f"{self.ENV_PREFIX}_LLM_UI_COMMAND_EXEC"] = ",".join(value)

    @property
    def LLM_UI_COMMAND_SET_MODEL(self) -> list[str]:
        return self._parse_command_list(
            get_env(
                "LLM_UI_COMMAND_SET_MODEL",
                self.DEFAULT_LLM_UI_COMMAND_SET_MODEL,
                self.ENV_PREFIX,
            )
        )

    @LLM_UI_COMMAND_SET_MODEL.setter
    def LLM_UI_COMMAND_SET_MODEL(self, value: list[str]):
        os.environ[f"{self.ENV_PREFIX}_LLM_UI_COMMAND_SET_MODEL"] = ",".join(value)

    @property
    def LLM_UI_COMMAND_BTW(self) -> list[str]:
        return self._parse_command_list(
            get_env(
                "LLM_UI_COMMAND_BTW",
                self.DEFAULT_LLM_UI_COMMAND_BTW,
                self.ENV_PREFIX,
            )
        )

    @LLM_UI_COMMAND_BTW.setter
    def LLM_UI_COMMAND_BTW(self, value: list[str]):
        os.environ[f"{self.ENV_PREFIX}_LLM_UI_COMMAND_BTW"] = ",".join(value)
