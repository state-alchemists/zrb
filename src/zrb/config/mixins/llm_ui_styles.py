"""LLM UI style and assistant-identity settings.

Style knobs take their defaults from the active theme (``CFG.THEME`` →
``config/theme.py``); an explicitly set ``ZRB_LLM_UI_STYLE_*`` env overrides the
theme. The three assistant-identity knobs are not themed.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from zrb.config.env_field import EnvField
from zrb.config.theme import theme_default


class LLMUIStylesMixin:
    if TYPE_CHECKING:
        # Attributes supplied by sibling mixins on the composed Config class.
        ENV_PREFIX: str  # FoundationMixin
        ROOT_GROUP_NAME: str  # FoundationMixin
        ROOT_GROUP_DESCRIPTION: str  # FoundationMixin
        THEME: str  # ThemeMixin

    def __init__(self) -> None:
        self.DEFAULT_LLM_ASSISTANT_NAME: str = "Zrb"
        self.DEFAULT_LLM_ASSISTANT_ASCII_ART: str = "default"
        self.DEFAULT_LLM_ASSISTANT_JARGON: str = ""
        super().__init__()

    # Falls back to ROOT_GROUP_NAME, then capitalizes the first letter while
    # preserving the rest ("boom" → "Boom", "CustomAssistant" unchanged).
    LLM_ASSISTANT_NAME = EnvField(
        str,
        default_factory=lambda c: c.DEFAULT_LLM_ASSISTANT_NAME or c.ROOT_GROUP_NAME,
        transform=lambda v, c: (v[0].upper() + v[1:]) if v else v,
        doc="Display name of the LLM assistant.",
    )

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
        str,
        default_factory=theme_default("LLM_UI_STYLE_TITLE_BAR"),
        doc="Prompt-toolkit foreground style for the UI title bar (hex or named style).",
    )

    LLM_UI_STYLE_TITLE_BAR_BG = EnvField(
        str,
        default_factory=theme_default("LLM_UI_STYLE_TITLE_BAR_BG"),
        doc="Prompt-toolkit background color for the UI title bar.",
    )

    LLM_UI_STYLE_INFO_BAR = EnvField(
        str,
        default_factory=theme_default("LLM_UI_STYLE_INFO_BAR"),
        doc="Prompt-toolkit style for the UI info bar.",
    )

    LLM_UI_STYLE_FRAME = EnvField(
        str,
        default_factory=theme_default("LLM_UI_STYLE_FRAME"),
        doc="Prompt-toolkit style for UI panel frame borders.",
    )

    LLM_UI_STYLE_FRAME_LABEL = EnvField(
        str,
        default_factory=theme_default("LLM_UI_STYLE_FRAME_LABEL"),
        doc="Prompt-toolkit style for UI panel frame label text.",
    )

    LLM_UI_STYLE_INPUT_FRAME = EnvField(
        str,
        default_factory=theme_default("LLM_UI_STYLE_INPUT_FRAME"),
        doc="Prompt-toolkit style for the input panel frame border.",
    )

    LLM_UI_STYLE_PROMPT = EnvField(
        str,
        default_factory=theme_default("LLM_UI_STYLE_PROMPT"),
        doc="Prompt-toolkit style for the input prompt marker (>>>).",
    )

    LLM_UI_STYLE_THINKING = EnvField(
        str,
        default_factory=theme_default("LLM_UI_STYLE_THINKING"),
        doc="Prompt-toolkit style for the 'thinking…' status indicator.",
    )

    LLM_UI_STYLE_CONFIRMATION = EnvField(
        str,
        default_factory=theme_default("LLM_UI_STYLE_CONFIRMATION"),
        doc="Prompt-toolkit style for the tool-call confirmation prompt.",
    )

    LLM_UI_STYLE_FAINT = EnvField(
        str,
        default_factory=theme_default("LLM_UI_STYLE_FAINT"),
        doc="Prompt-toolkit style for de-emphasized (faint) text.",
    )

    LLM_UI_STYLE_OUTPUT_FIELD = EnvField(
        str,
        default_factory=theme_default("LLM_UI_STYLE_OUTPUT_FIELD"),
        doc="Prompt-toolkit style for the read-only output text area.",
    )

    LLM_UI_STYLE_INPUT_FIELD = EnvField(
        str,
        default_factory=theme_default("LLM_UI_STYLE_INPUT_FIELD"),
        doc="Prompt-toolkit style for the user input text area.",
    )

    LLM_UI_STYLE_TEXT = EnvField(
        str,
        default_factory=theme_default("LLM_UI_STYLE_TEXT"),
        doc="Prompt-toolkit style for general body text.",
    )

    LLM_UI_STYLE_STATUS = EnvField(
        str,
        default_factory=theme_default("LLM_UI_STYLE_STATUS"),
        doc="Prompt-toolkit style for the status bar text.",
    )

    LLM_UI_STYLE_BOTTOM_TOOLBAR = EnvField(
        str,
        default_factory=theme_default("LLM_UI_STYLE_BOTTOM_TOOLBAR"),
        doc="Prompt-toolkit style for the bottom toolbar. 'noinherit' resets to terminal defaults.",
    )

    # Choice widget (AskUserQuestion selection panel)
    LLM_UI_STYLE_CHOICE_BG = EnvField(
        str,
        default_factory=theme_default("LLM_UI_STYLE_CHOICE_BG"),
        doc="Background color for the choice widget panel.",
    )

    LLM_UI_STYLE_CHOICE_SELECTED_BG = EnvField(
        str,
        default_factory=theme_default("LLM_UI_STYLE_CHOICE_SELECTED_BG"),
        doc="Background color for the selected item in the choice widget.",
    )

    # Status-bar mode badge styles (Shift+Tab mode indicator)
    LLM_UI_STYLE_MODE_NORMAL = EnvField(
        str,
        default_factory=theme_default("LLM_UI_STYLE_MODE_NORMAL"),
        doc="Status-bar badge style for normal mode.",
    )

    LLM_UI_STYLE_MODE_ACCEPT_EDITS = EnvField(
        str,
        default_factory=theme_default("LLM_UI_STYLE_MODE_ACCEPT_EDITS"),
        doc="Status-bar badge style for accept-edits mode.",
    )

    LLM_UI_STYLE_MODE_PLAN = EnvField(
        str,
        default_factory=theme_default("LLM_UI_STYLE_MODE_PLAN"),
        doc="Status-bar badge style for plan mode.",
    )

    LLM_UI_STYLE_MODE_YOLO = EnvField(
        str,
        default_factory=theme_default("LLM_UI_STYLE_MODE_YOLO"),
        doc="Status-bar badge style for YOLO mode.",
    )

    LLM_UI_STYLE_MODE_CUSTOM = EnvField(
        str,
        default_factory=theme_default("LLM_UI_STYLE_MODE_CUSTOM"),
        doc="Status-bar badge style for custom-YOLO mode.",
    )

    # Info-bar YOLO/Plan mode indicator colors
    LLM_UI_STYLE_INFO_YOLO_ON = EnvField(
        str,
        default_factory=theme_default("LLM_UI_STYLE_INFO_YOLO_ON"),
        doc="Info-bar style when YOLO mode is fully on.",
    )

    LLM_UI_STYLE_INFO_YOLO_PARTIAL = EnvField(
        str,
        default_factory=theme_default("LLM_UI_STYLE_INFO_YOLO_PARTIAL"),
        doc="Info-bar style when YOLO mode is partially enabled (specific tools only).",
    )

    LLM_UI_STYLE_INFO_YOLO_OFF = EnvField(
        str,
        default_factory=theme_default("LLM_UI_STYLE_INFO_YOLO_OFF"),
        doc="Info-bar style when YOLO mode is off.",
    )

    LLM_UI_STYLE_INFO_PLAN_ON = EnvField(
        str,
        default_factory=theme_default("LLM_UI_STYLE_INFO_PLAN_ON"),
        doc="Info-bar style when plan mode is active.",
    )

    LLM_UI_STYLE_INFO_PLAN_OFF = EnvField(
        str,
        default_factory=theme_default("LLM_UI_STYLE_INFO_PLAN_OFF"),
        doc="Info-bar style when plan mode is inactive.",
    )

    # Markdown rendering (Rich style strings; consumed by util/cli/markdown.py)
    LLM_UI_STYLE_MARKDOWN_LINK = EnvField(
        str,
        default_factory=theme_default("LLM_UI_STYLE_MARKDOWN_LINK"),
        doc="Rich style for markdown link text.",
    )

    LLM_UI_STYLE_MARKDOWN_LINK_URL = EnvField(
        str,
        default_factory=theme_default("LLM_UI_STYLE_MARKDOWN_LINK_URL"),
        doc="Rich style for markdown link URLs.",
    )

    LLM_UI_STYLE_MARKDOWN_H1 = EnvField(
        str,
        default_factory=theme_default("LLM_UI_STYLE_MARKDOWN_H1"),
        doc="Rich style for markdown level-1 headings.",
    )

    LLM_UI_STYLE_MARKDOWN_CODE = EnvField(
        str,
        default_factory=theme_default("LLM_UI_STYLE_MARKDOWN_CODE"),
        doc="Rich style for inline markdown code spans.",
    )
