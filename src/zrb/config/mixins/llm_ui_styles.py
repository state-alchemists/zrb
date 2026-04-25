"""LLM UI style and assistant-identity settings (12 colour styles + 3 identity props)."""

from __future__ import annotations

import os

from zrb.config.helper import get_env


class LLMUIStylesMixin:
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
