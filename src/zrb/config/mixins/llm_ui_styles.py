"""LLM UI style and assistant-identity settings (12 colour styles + 3 identity props)."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Protocol

from zrb.config.env_field import EnvField
from zrb.config.helper import get_env

if TYPE_CHECKING:

    class _LLMUIStylesHost(Protocol):
        """Attributes this mixin expects from the composed Config class."""

        ENV_PREFIX: str
        ROOT_GROUP_NAME: str
        ROOT_GROUP_DESCRIPTION: str


class LLMUIStylesMixin:
    def __init__(self) -> None:
        self.DEFAULT_LLM_ASSISTANT_NAME: str = "Zrb"
        self.DEFAULT_LLM_ASSISTANT_ASCII_ART: str = "default"
        self.DEFAULT_LLM_ASSISTANT_JARGON: str = ""
        self.DEFAULT_LLM_UI_STYLE_TITLE_BAR: str = "#ffffff"
        self.DEFAULT_LLM_UI_STYLE_INFO_BAR: str = "#ffffff"
        self.DEFAULT_LLM_UI_STYLE_FRAME: str = "#888888"
        self.DEFAULT_LLM_UI_STYLE_FRAME_LABEL: str = "#ffff00"
        self.DEFAULT_LLM_UI_STYLE_INPUT_FRAME: str = "#888888"
        self.DEFAULT_LLM_UI_STYLE_THINKING: str = "ansigreen"
        self.DEFAULT_LLM_UI_STYLE_CONFIRMATION: str = "ansiyellow"
        self.DEFAULT_LLM_UI_STYLE_FAINT: str = "#888888"
        self.DEFAULT_LLM_UI_STYLE_OUTPUT_FIELD: str = "#eeeeee"
        self.DEFAULT_LLM_UI_STYLE_INPUT_FIELD: str = "#eeeeee"
        self.DEFAULT_LLM_UI_STYLE_TEXT: str = "#eeeeee"
        self.DEFAULT_LLM_UI_STYLE_STATUS: str = "ansiwhite"
        # Do not inherit prompt_toolkit's default pale bottom toolbar styling.
        # "noinherit" resets to terminal defaults (no fg/bg/bold) so only
        # fragment styles control the text color.
        self.DEFAULT_LLM_UI_STYLE_BOTTOM_TOOLBAR: str = "noinherit"
        super().__init__()

    # Hand-written: falls back to ROOT_GROUP_NAME and capitalizes the first
    # letter (preserving the rest), which EnvField's plain read cannot express.
    @property
    def LLM_ASSISTANT_NAME(self: _LLMUIStylesHost) -> str:
        default = self.DEFAULT_LLM_ASSISTANT_NAME
        if default == "":
            default = self.ROOT_GROUP_NAME
        raw = get_env("LLM_ASSISTANT_NAME", default, self.ENV_PREFIX)
        # Capitalize first letter — preserves existing casing on the rest
        # (e.g. "boom" → "Boom", "CustomAssistant" → "CustomAssistant")
        return raw[0].upper() + raw[1:] if raw else raw

    @LLM_ASSISTANT_NAME.setter
    def LLM_ASSISTANT_NAME(self: _LLMUIStylesHost, value: str) -> None:
        os.environ[f"{self.ENV_PREFIX}_LLM_ASSISTANT_NAME"] = value

    LLM_ASSISTANT_ASCII_ART = EnvField(str)

    LLM_ASSISTANT_JARGON = EnvField(
        str,
        default_factory=lambda cfg: (
            cfg.DEFAULT_LLM_ASSISTANT_JARGON or cfg.ROOT_GROUP_DESCRIPTION
        ),
    )

    LLM_UI_STYLE_TITLE_BAR = EnvField(str)

    LLM_UI_STYLE_INFO_BAR = EnvField(str)

    LLM_UI_STYLE_FRAME = EnvField(str)

    LLM_UI_STYLE_FRAME_LABEL = EnvField(str)

    LLM_UI_STYLE_INPUT_FRAME = EnvField(str)

    LLM_UI_STYLE_THINKING = EnvField(str)

    LLM_UI_STYLE_CONFIRMATION = EnvField(str)

    LLM_UI_STYLE_FAINT = EnvField(str)

    LLM_UI_STYLE_OUTPUT_FIELD = EnvField(str)

    LLM_UI_STYLE_INPUT_FIELD = EnvField(str)

    LLM_UI_STYLE_TEXT = EnvField(str)

    LLM_UI_STYLE_STATUS = EnvField(str)

    LLM_UI_STYLE_BOTTOM_TOOLBAR = EnvField(str)
