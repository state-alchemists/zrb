"""LLM UI style and assistant-identity settings (26 colour styles + 3 identity props)."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from zrb.config.env_field import EnvField
from zrb.config.helper import get_env


class LLMUIStylesMixin:
    if TYPE_CHECKING:
        # Attributes supplied by sibling mixins on the composed Config class.
        ENV_PREFIX: str  # FoundationMixin
        ROOT_GROUP_NAME: str  # FoundationMixin
        ROOT_GROUP_DESCRIPTION: str  # FoundationMixin

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
        # Choice widget (AskUserQuestion selection panel)
        self.DEFAULT_LLM_UI_STYLE_CHOICE_BG: str = "#1f1f1f"
        self.DEFAULT_LLM_UI_STYLE_CHOICE_SELECTED_BG: str = "#264f78"
        # Status-bar mode badge styles (Shift+Tab mode indicator)
        self.DEFAULT_LLM_UI_STYLE_MODE_NORMAL: str = "fg:ansigreen"
        self.DEFAULT_LLM_UI_STYLE_MODE_ACCEPT_EDITS: str = "fg:ansiyellow bold"
        self.DEFAULT_LLM_UI_STYLE_MODE_PLAN: str = "fg:ansiblue bold"
        self.DEFAULT_LLM_UI_STYLE_MODE_YOLO: str = "fg:ansired bold"
        self.DEFAULT_LLM_UI_STYLE_MODE_CUSTOM: str = "fg:ansiyellow bold"
        # Info-bar YOLO/Plan mode indicator colors
        self.DEFAULT_LLM_UI_STYLE_INFO_YOLO_ON: str = "ansired"
        self.DEFAULT_LLM_UI_STYLE_INFO_YOLO_PARTIAL: str = "ansiyellow"
        self.DEFAULT_LLM_UI_STYLE_INFO_YOLO_OFF: str = "ansigreen"
        self.DEFAULT_LLM_UI_STYLE_INFO_PLAN_ON: str = "ansiblue"
        self.DEFAULT_LLM_UI_STYLE_INFO_PLAN_OFF: str = "ansigreen"
        super().__init__()

    # Hand-written: falls back to ROOT_GROUP_NAME and capitalizes the first
    # letter (preserving the rest), which EnvField's plain read cannot express.
    @property
    def LLM_ASSISTANT_NAME(self) -> str:
        default = self.DEFAULT_LLM_ASSISTANT_NAME
        if default == "":
            default = self.ROOT_GROUP_NAME
        raw = get_env("LLM_ASSISTANT_NAME", default, self.ENV_PREFIX)
        # Capitalize first letter — preserves existing casing on the rest
        # (e.g. "boom" → "Boom", "CustomAssistant" → "CustomAssistant")
        return raw[0].upper() + raw[1:] if raw else raw

    @LLM_ASSISTANT_NAME.setter
    def LLM_ASSISTANT_NAME(self, value: str) -> None:
        os.environ[f"{self.ENV_PREFIX}_LLM_ASSISTANT_NAME"] = value

    LLM_ASSISTANT_ASCII_ART = EnvField(
        str, doc="Name of the ASCII art variant displayed in the LLM UI title bar."
    )

    LLM_ASSISTANT_JARGON = EnvField(
        str,
        default_factory=lambda cfg: (
            cfg.DEFAULT_LLM_ASSISTANT_JARGON or cfg.ROOT_GROUP_DESCRIPTION
        ),
        doc="Tagline shown beneath the assistant name in the LLM UI title bar.",
    )

    LLM_UI_STYLE_TITLE_BAR = EnvField(
        str, doc="Prompt-toolkit style for the UI title bar (hex color or named style)."
    )

    LLM_UI_STYLE_INFO_BAR = EnvField(
        str, doc="Prompt-toolkit style for the UI info bar."
    )

    LLM_UI_STYLE_FRAME = EnvField(
        str, doc="Prompt-toolkit style for UI panel frame borders."
    )

    LLM_UI_STYLE_FRAME_LABEL = EnvField(
        str, doc="Prompt-toolkit style for UI panel frame label text."
    )

    LLM_UI_STYLE_INPUT_FRAME = EnvField(
        str, doc="Prompt-toolkit style for the input panel frame border."
    )

    LLM_UI_STYLE_THINKING = EnvField(
        str, doc="Prompt-toolkit style for the 'thinking…' status indicator."
    )

    LLM_UI_STYLE_CONFIRMATION = EnvField(
        str, doc="Prompt-toolkit style for the tool-call confirmation prompt."
    )

    LLM_UI_STYLE_FAINT = EnvField(
        str, doc="Prompt-toolkit style for de-emphasized (faint) text."
    )

    LLM_UI_STYLE_OUTPUT_FIELD = EnvField(
        str, doc="Prompt-toolkit style for the read-only output text area."
    )

    LLM_UI_STYLE_INPUT_FIELD = EnvField(
        str, doc="Prompt-toolkit style for the user input text area."
    )

    LLM_UI_STYLE_TEXT = EnvField(str, doc="Prompt-toolkit style for general body text.")

    LLM_UI_STYLE_STATUS = EnvField(
        str, doc="Prompt-toolkit style for the status bar text."
    )

    LLM_UI_STYLE_BOTTOM_TOOLBAR = EnvField(
        str,
        doc="Prompt-toolkit style for the bottom toolbar. 'noinherit' resets to terminal defaults.",
    )

    # Choice widget (AskUserQuestion selection panel)
    LLM_UI_STYLE_CHOICE_BG = EnvField(
        str, doc="Background color for the choice widget panel."
    )

    LLM_UI_STYLE_CHOICE_SELECTED_BG = EnvField(
        str, doc="Background color for the selected item in the choice widget."
    )

    # Status-bar mode badge styles (Shift+Tab mode indicator)
    LLM_UI_STYLE_MODE_NORMAL = EnvField(
        str, doc="Status-bar badge style for normal mode."
    )

    LLM_UI_STYLE_MODE_ACCEPT_EDITS = EnvField(
        str, doc="Status-bar badge style for accept-edits mode."
    )

    LLM_UI_STYLE_MODE_PLAN = EnvField(str, doc="Status-bar badge style for plan mode.")

    LLM_UI_STYLE_MODE_YOLO = EnvField(str, doc="Status-bar badge style for YOLO mode.")

    LLM_UI_STYLE_MODE_CUSTOM = EnvField(
        str, doc="Status-bar badge style for custom-YOLO mode."
    )

    # Info-bar YOLO/Plan mode indicator colors
    LLM_UI_STYLE_INFO_YOLO_ON = EnvField(
        str, doc="Info-bar style when YOLO mode is fully on."
    )

    LLM_UI_STYLE_INFO_YOLO_PARTIAL = EnvField(
        str,
        doc="Info-bar style when YOLO mode is partially enabled (specific tools only).",
    )

    LLM_UI_STYLE_INFO_YOLO_OFF = EnvField(
        str, doc="Info-bar style when YOLO mode is off."
    )

    LLM_UI_STYLE_INFO_PLAN_ON = EnvField(
        str, doc="Info-bar style when plan mode is active."
    )

    LLM_UI_STYLE_INFO_PLAN_OFF = EnvField(
        str, doc="Info-bar style when plan mode is inactive."
    )
