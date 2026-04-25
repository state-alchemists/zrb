"""LLM UI config: assistant identity, colour styles, slash-command aliases, intervals, buffer size."""

from __future__ import annotations

import os

from zrb.config.helper import get_env


class LLMUIMixin:
    def __init__(self):
        self.DEFAULT_LLM_ASSISTANT_NAME: str = ""
        self.DEFAULT_LLM_ASSISTANT_ASCII_ART: str = "default"
        self.DEFAULT_LLM_ASSISTANT_JARGON: str = ""
        self.DEFAULT_LLM_UI_STYLE_TITLE_BAR: str = "#ffffff"
        self.DEFAULT_LLM_UI_STYLE_INFO_BAR: str = "#ffffff"
        self.DEFAULT_LLM_UI_STYLE_FRAME: str = "#888888"
        self.DEFAULT_LLM_UI_STYLE_FRAME_LABEL: str = "#ffff00"
        self.DEFAULT_LLM_UI_STYLE_INPUT_FRAME: str = "#888888"
        self.DEFAULT_LLM_UI_STYLE_THINKING: str = "ansigreen italic"
        self.DEFAULT_LLM_UI_STYLE_FAINT: str = "#888888"
        self.DEFAULT_LLM_UI_STYLE_OUTPUT_FIELD: str = "#eeeeee"
        self.DEFAULT_LLM_UI_STYLE_INPUT_FIELD: str = "#eeeeee"
        self.DEFAULT_LLM_UI_STYLE_TEXT: str = "#eeeeee"
        self.DEFAULT_LLM_UI_STYLE_STATUS: str = "reverse"
        self.DEFAULT_LLM_UI_STYLE_BOTTOM_TOOLBAR: str = "bg:#333333 #aaaaaa"
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
        self.DEFAULT_LLM_UI_STATUS_INTERVAL: str = "1000"
        self.DEFAULT_LLM_UI_LONG_STATUS_INTERVAL: str = "60000"
        self.DEFAULT_LLM_UI_REFRESH_INTERVAL: str = "500"
        self.DEFAULT_LLM_UI_FLUSH_INTERVAL: str = "500"
        self.DEFAULT_LLM_UI_MAX_BUFFER_SIZE: str = "2000"
        super().__init__()

    @property
    def LLM_ASSISTANT_NAME(self) -> str:
        default = self.DEFAULT_LLM_ASSISTANT_NAME
        if default == "":
            default = self.ROOT_GROUP_NAME
        return get_env("LLM_ASSISTANT_NAME", default, self.ENV_PREFIX)

    @LLM_ASSISTANT_NAME.setter
    def LLM_ASSISTANT_NAME(self, value: str):
        os.environ[f"{self.ENV_PREFIX}_LLM_ASSISTANT_NAME"] = value

    @property
    def LLM_ASSISTANT_ASCII_ART(self) -> str:
        return get_env(
            "LLM_ASSISTANT_ASCII_ART",
            self.DEFAULT_LLM_ASSISTANT_ASCII_ART,
            self.ENV_PREFIX,
        )

    @LLM_ASSISTANT_ASCII_ART.setter
    def LLM_ASSISTANT_ASCII_ART(self, value: str):
        os.environ[f"{self.ENV_PREFIX}_LLM_ASSISTANT_ASCII_ART"] = value

    @property
    def LLM_ASSISTANT_JARGON(self) -> str:
        default = self.DEFAULT_LLM_ASSISTANT_JARGON
        if default == "":
            default = self.ROOT_GROUP_DESCRIPTION
        return get_env("LLM_ASSISTANT_JARGON", default, self.ENV_PREFIX)

    @LLM_ASSISTANT_JARGON.setter
    def LLM_ASSISTANT_JARGON(self, value: str):
        os.environ[f"{self.ENV_PREFIX}_LLM_ASSISTANT_JARGON"] = value

    # --- Styles ------------------------------------------------------------

    @property
    def LLM_UI_STYLE_TITLE_BAR(self) -> str:
        return get_env(
            "LLM_UI_STYLE_TITLE_BAR",
            self.DEFAULT_LLM_UI_STYLE_TITLE_BAR,
            self.ENV_PREFIX,
        )

    @LLM_UI_STYLE_TITLE_BAR.setter
    def LLM_UI_STYLE_TITLE_BAR(self, value: str):
        os.environ[f"{self.ENV_PREFIX}_LLM_UI_STYLE_TITLE_BAR"] = value

    @property
    def LLM_UI_STYLE_INFO_BAR(self) -> str:
        return get_env(
            "LLM_UI_STYLE_INFO_BAR", self.DEFAULT_LLM_UI_STYLE_INFO_BAR, self.ENV_PREFIX
        )

    @LLM_UI_STYLE_INFO_BAR.setter
    def LLM_UI_STYLE_INFO_BAR(self, value: str):
        os.environ[f"{self.ENV_PREFIX}_LLM_UI_STYLE_INFO_BAR"] = value

    @property
    def LLM_UI_STYLE_FRAME(self) -> str:
        return get_env(
            "LLM_UI_STYLE_FRAME", self.DEFAULT_LLM_UI_STYLE_FRAME, self.ENV_PREFIX
        )

    @LLM_UI_STYLE_FRAME.setter
    def LLM_UI_STYLE_FRAME(self, value: str):
        os.environ[f"{self.ENV_PREFIX}_LLM_UI_STYLE_FRAME"] = value

    @property
    def LLM_UI_STYLE_FRAME_LABEL(self) -> str:
        return get_env(
            "LLM_UI_STYLE_FRAME_LABEL",
            self.DEFAULT_LLM_UI_STYLE_FRAME_LABEL,
            self.ENV_PREFIX,
        )

    @LLM_UI_STYLE_FRAME_LABEL.setter
    def LLM_UI_STYLE_FRAME_LABEL(self, value: str):
        os.environ[f"{self.ENV_PREFIX}_LLM_UI_STYLE_FRAME_LABEL"] = value

    @property
    def LLM_UI_STYLE_INPUT_FRAME(self) -> str:
        return get_env(
            "LLM_UI_STYLE_INPUT_FRAME",
            self.DEFAULT_LLM_UI_STYLE_INPUT_FRAME,
            self.ENV_PREFIX,
        )

    @LLM_UI_STYLE_INPUT_FRAME.setter
    def LLM_UI_STYLE_INPUT_FRAME(self, value: str):
        os.environ[f"{self.ENV_PREFIX}_LLM_UI_STYLE_INPUT_FRAME"] = value

    @property
    def LLM_UI_STYLE_THINKING(self) -> str:
        return get_env(
            "LLM_UI_STYLE_THINKING", self.DEFAULT_LLM_UI_STYLE_THINKING, self.ENV_PREFIX
        )

    @LLM_UI_STYLE_THINKING.setter
    def LLM_UI_STYLE_THINKING(self, value: str):
        os.environ[f"{self.ENV_PREFIX}_LLM_UI_STYLE_THINKING"] = value

    @property
    def LLM_UI_STYLE_FAINT(self) -> str:
        return get_env(
            "LLM_UI_STYLE_FAINT", self.DEFAULT_LLM_UI_STYLE_FAINT, self.ENV_PREFIX
        )

    @LLM_UI_STYLE_FAINT.setter
    def LLM_UI_STYLE_FAINT(self, value: str):
        os.environ[f"{self.ENV_PREFIX}_LLM_UI_STYLE_FAINT"] = value

    @property
    def LLM_UI_STYLE_OUTPUT_FIELD(self) -> str:
        return get_env(
            "LLM_UI_STYLE_OUTPUT_FIELD",
            self.DEFAULT_LLM_UI_STYLE_OUTPUT_FIELD,
            self.ENV_PREFIX,
        )

    @LLM_UI_STYLE_OUTPUT_FIELD.setter
    def LLM_UI_STYLE_OUTPUT_FIELD(self, value: str):
        os.environ[f"{self.ENV_PREFIX}_LLM_UI_STYLE_OUTPUT_FIELD"] = value

    @property
    def LLM_UI_STYLE_INPUT_FIELD(self) -> str:
        return get_env(
            "LLM_UI_STYLE_INPUT_FIELD",
            self.DEFAULT_LLM_UI_STYLE_INPUT_FIELD,
            self.ENV_PREFIX,
        )

    @LLM_UI_STYLE_INPUT_FIELD.setter
    def LLM_UI_STYLE_INPUT_FIELD(self, value: str):
        os.environ[f"{self.ENV_PREFIX}_LLM_UI_STYLE_INPUT_FIELD"] = value

    @property
    def LLM_UI_STYLE_TEXT(self) -> str:
        return get_env(
            "LLM_UI_STYLE_TEXT", self.DEFAULT_LLM_UI_STYLE_TEXT, self.ENV_PREFIX
        )

    @LLM_UI_STYLE_TEXT.setter
    def LLM_UI_STYLE_TEXT(self, value: str):
        os.environ[f"{self.ENV_PREFIX}_LLM_UI_STYLE_TEXT"] = value

    @property
    def LLM_UI_STYLE_STATUS(self) -> str:
        return get_env(
            "LLM_UI_STYLE_STATUS", self.DEFAULT_LLM_UI_STYLE_STATUS, self.ENV_PREFIX
        )

    @LLM_UI_STYLE_STATUS.setter
    def LLM_UI_STYLE_STATUS(self, value: str):
        os.environ[f"{self.ENV_PREFIX}_LLM_UI_STYLE_STATUS"] = value

    @property
    def LLM_UI_STYLE_BOTTOM_TOOLBAR(self) -> str:
        return get_env(
            "LLM_UI_STYLE_BOTTOM_TOOLBAR",
            self.DEFAULT_LLM_UI_STYLE_BOTTOM_TOOLBAR,
            self.ENV_PREFIX,
        )

    @LLM_UI_STYLE_BOTTOM_TOOLBAR.setter
    def LLM_UI_STYLE_BOTTOM_TOOLBAR(self, value: str):
        os.environ[f"{self.ENV_PREFIX}_LLM_UI_STYLE_BOTTOM_TOOLBAR"] = value

    # --- Commands ----------------------------------------------------------

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

    # --- Intervals / buffers ----------------------------------------------

    @property
    def LLM_UI_STATUS_INTERVAL(self) -> int:
        """Interval in milliseconds for UI status checks."""
        return int(
            get_env(
                "LLM_UI_STATUS_INTERVAL",
                self.DEFAULT_LLM_UI_STATUS_INTERVAL,
                self.ENV_PREFIX,
            )
        )

    @LLM_UI_STATUS_INTERVAL.setter
    def LLM_UI_STATUS_INTERVAL(self, value: int):
        os.environ[f"{self.ENV_PREFIX}_LLM_UI_STATUS_INTERVAL"] = str(value)

    @property
    def LLM_UI_LONG_STATUS_INTERVAL(self) -> int:
        """Interval in milliseconds for long-running UI status checks."""
        return int(
            get_env(
                "LLM_UI_LONG_STATUS_INTERVAL",
                self.DEFAULT_LLM_UI_LONG_STATUS_INTERVAL,
                self.ENV_PREFIX,
            )
        )

    @LLM_UI_LONG_STATUS_INTERVAL.setter
    def LLM_UI_LONG_STATUS_INTERVAL(self, value: int):
        os.environ[f"{self.ENV_PREFIX}_LLM_UI_LONG_STATUS_INTERVAL"] = str(value)

    @property
    def LLM_UI_REFRESH_INTERVAL(self) -> int:
        """Interval in milliseconds for UI refresh."""
        return int(
            get_env(
                "LLM_UI_REFRESH_INTERVAL",
                self.DEFAULT_LLM_UI_REFRESH_INTERVAL,
                self.ENV_PREFIX,
            )
        )

    @LLM_UI_REFRESH_INTERVAL.setter
    def LLM_UI_REFRESH_INTERVAL(self, value: int):
        os.environ[f"{self.ENV_PREFIX}_LLM_UI_REFRESH_INTERVAL"] = str(value)

    @property
    def LLM_UI_FLUSH_INTERVAL(self) -> int:
        """Interval in milliseconds for UI buffer flush."""
        return int(
            get_env(
                "LLM_UI_FLUSH_INTERVAL",
                self.DEFAULT_LLM_UI_FLUSH_INTERVAL,
                self.ENV_PREFIX,
            )
        )

    @LLM_UI_FLUSH_INTERVAL.setter
    def LLM_UI_FLUSH_INTERVAL(self, value: int):
        os.environ[f"{self.ENV_PREFIX}_LLM_UI_FLUSH_INTERVAL"] = str(value)

    @property
    def LLM_UI_MAX_BUFFER_SIZE(self) -> int:
        """Maximum buffer size for UI output."""
        return int(
            get_env(
                "LLM_UI_MAX_BUFFER_SIZE",
                self.DEFAULT_LLM_UI_MAX_BUFFER_SIZE,
                self.ENV_PREFIX,
            )
        )

    @LLM_UI_MAX_BUFFER_SIZE.setter
    def LLM_UI_MAX_BUFFER_SIZE(self, value: int):
        os.environ[f"{self.ENV_PREFIX}_LLM_UI_MAX_BUFFER_SIZE"] = str(value)
