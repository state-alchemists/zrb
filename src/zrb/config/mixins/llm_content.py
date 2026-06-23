"""LLM content: history, snapshot, journal dirs, summarization thresholds, file read limits."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from zrb.config.env_field import EnvField, on_off
from zrb.config.helper import get_max_token_threshold, limit_token_threshold
from zrb.util.string.conversion import to_boolean


class LLMContentMixin:
    if TYPE_CHECKING:
        # Attributes supplied by sibling mixins on the composed Config class.
        ENV_PREFIX: str  # FoundationMixin
        ROOT_GROUP_NAME: str  # FoundationMixin
        LLM_MAX_TOKEN_PER_MINUTE: int  # LLMLimitsMixin
        LLM_MAX_TOKEN_PER_REQUEST: int  # LLMLimitsMixin

    def __init__(self) -> None:
        self.DEFAULT_LLM_HISTORY_DIR: str = ""
        self.DEFAULT_LLM_HISTORY_BACKUP_RETAIN: str = "3"
        self.DEFAULT_LLM_ENABLE_REWIND: str = "off"
        self.DEFAULT_LLM_SNAPSHOT_DIR: str = ""
        self.DEFAULT_LLM_JOURNAL_DIR: str = ""
        self.DEFAULT_LLM_JOURNAL_INDEX_FILE: str = "index.md"
        self.DEFAULT_LLM_HISTORY_SUMMARIZATION_WINDOW: str = "100"
        self.DEFAULT_LLM_CONVERSATIONAL_SUMMARIZATION_TOKEN_THRESHOLD: str = ""
        self.DEFAULT_LLM_MESSAGE_SUMMARIZATION_TOKEN_THRESHOLD: str = ""
        self.DEFAULT_LLM_REPO_ANALYSIS_EXTRACTION_TOKEN_THRESHOLD: str = ""
        self.DEFAULT_LLM_REPO_ANALYSIS_SUMMARIZATION_TOKEN_THRESHOLD: str = ""
        self.DEFAULT_LLM_FILE_ANALYSIS_TOKEN_THRESHOLD: str = ""
        self.DEFAULT_LLM_HISTORY_MAX_DISPLAY_CHARS: str = "5000"
        self.DEFAULT_LLM_HISTORY_TRUNCATE_LENGTH: str = "100"
        self.DEFAULT_LLM_FILE_READ_LINES: str = "1000"
        super().__init__()

    LLM_HISTORY_DIR = EnvField(
        str,
        default_factory=lambda cfg: (
            cfg.DEFAULT_LLM_HISTORY_DIR
            if cfg.DEFAULT_LLM_HISTORY_DIR
            else os.path.expanduser(
                os.path.join("~", f".{cfg.ROOT_GROUP_NAME}", "llm-history")
            )
        ),
        doc="Directory for LLM conversation history files.",
    )

    LLM_SNAPSHOT_DIR = EnvField(
        str,
        default_factory=lambda cfg: (
            cfg.DEFAULT_LLM_SNAPSHOT_DIR
            if cfg.DEFAULT_LLM_SNAPSHOT_DIR
            else os.path.expanduser(
                os.path.join("~", f".{cfg.ROOT_GROUP_NAME}", "llm-snapshots")
            )
        ),
        doc="Directory for LLM conversation snapshots.",
    )

    LLM_JOURNAL_DIR = EnvField(
        str,
        default_factory=lambda cfg: (
            cfg.DEFAULT_LLM_JOURNAL_DIR
            if cfg.DEFAULT_LLM_JOURNAL_DIR
            else os.path.expanduser(
                os.path.join("~", f".{cfg.ROOT_GROUP_NAME}", "llm-notes")
            )
        ),
        doc="Directory for LLM journal/notes.",
    )

    LLM_JOURNAL_INDEX_FILE = EnvField(
        str,
        default_factory=lambda cfg: cfg.DEFAULT_LLM_JOURNAL_INDEX_FILE,
        doc="Filename of the journal index file.",
    )

    LLM_ENABLE_REWIND = EnvField(
        to_boolean,
        serialize=on_off,
        default_factory=lambda cfg: cfg.DEFAULT_LLM_ENABLE_REWIND,
        doc="Enable/disable the rewind feature for LLM conversations.",
    )

    LLM_HISTORY_BACKUP_RETAIN = EnvField(
        int,
        fallback=0,
        default_factory=lambda cfg: cfg.DEFAULT_LLM_HISTORY_BACKUP_RETAIN,
        doc=(
            "Number of timestamped history backups to keep per conversation. "
            "0 disables backup writes entirely. -1 keeps every backup "
            "(legacy behavior)."
        ),
    )

    LLM_HISTORY_SUMMARIZATION_WINDOW = EnvField(
        int,
        fallback=0,
        default_factory=lambda cfg: cfg.DEFAULT_LLM_HISTORY_SUMMARIZATION_WINDOW,
        doc="Number of turns before summarization is triggered.",
    )

    LLM_HISTORY_MAX_DISPLAY_CHARS = EnvField(
        int,
        fallback=0,
        default_factory=lambda cfg: cfg.DEFAULT_LLM_HISTORY_MAX_DISPLAY_CHARS,
        doc="Maximum characters to display in history.",
    )

    LLM_HISTORY_TRUNCATE_LENGTH = EnvField(
        int,
        fallback=0,
        default_factory=lambda cfg: cfg.DEFAULT_LLM_HISTORY_TRUNCATE_LENGTH,
        doc="Character length for history truncation.",
    )

    LLM_FILE_READ_LINES = EnvField(
        int,
        fallback=0,
        default_factory=lambda cfg: cfg.DEFAULT_LLM_FILE_READ_LINES,
        doc="Default number of lines to read from files (head/tail).",
    )

    LLM_CONVERSATIONAL_SUMMARIZATION_TOKEN_THRESHOLD = EnvField(
        int,
        transform=lambda v, cfg: limit_token_threshold(
            v, 0.6, cfg.LLM_MAX_TOKEN_PER_MINUTE, cfg.LLM_MAX_TOKEN_PER_REQUEST
        ),
        default_factory=lambda cfg: (
            cfg.DEFAULT_LLM_CONVERSATIONAL_SUMMARIZATION_TOKEN_THRESHOLD
            or str(
                get_max_token_threshold(
                    0.6,
                    cfg.LLM_MAX_TOKEN_PER_MINUTE,
                    cfg.LLM_MAX_TOKEN_PER_REQUEST,
                )
            )
        ),
        doc="Token threshold for conversational summarization.",
    )

    LLM_MESSAGE_SUMMARIZATION_TOKEN_THRESHOLD = EnvField(
        int,
        transform=lambda v, cfg: limit_token_threshold(
            v, 0.6, cfg.LLM_MAX_TOKEN_PER_MINUTE, cfg.LLM_MAX_TOKEN_PER_REQUEST
        ),
        default_factory=lambda cfg: (
            cfg.DEFAULT_LLM_MESSAGE_SUMMARIZATION_TOKEN_THRESHOLD
            or str(cfg.LLM_CONVERSATIONAL_SUMMARIZATION_TOKEN_THRESHOLD // 2)
        ),
        doc="Token threshold for message summarization.",
    )

    LLM_REPO_ANALYSIS_EXTRACTION_TOKEN_THRESHOLD = EnvField(
        int,
        transform=lambda v, cfg: limit_token_threshold(
            v, 0.4, cfg.LLM_MAX_TOKEN_PER_MINUTE, cfg.LLM_MAX_TOKEN_PER_REQUEST
        ),
        default_factory=lambda cfg: (
            cfg.DEFAULT_LLM_REPO_ANALYSIS_EXTRACTION_TOKEN_THRESHOLD
            or str(
                get_max_token_threshold(
                    0.4,
                    cfg.LLM_MAX_TOKEN_PER_MINUTE,
                    cfg.LLM_MAX_TOKEN_PER_REQUEST,
                )
            )
        ),
        doc="Token threshold for repo analysis extraction.",
    )

    LLM_REPO_ANALYSIS_SUMMARIZATION_TOKEN_THRESHOLD = EnvField(
        int,
        transform=lambda v, cfg: limit_token_threshold(
            v, 0.4, cfg.LLM_MAX_TOKEN_PER_MINUTE, cfg.LLM_MAX_TOKEN_PER_REQUEST
        ),
        default_factory=lambda cfg: (
            cfg.DEFAULT_LLM_REPO_ANALYSIS_SUMMARIZATION_TOKEN_THRESHOLD
            or str(
                get_max_token_threshold(
                    0.4,
                    cfg.LLM_MAX_TOKEN_PER_MINUTE,
                    cfg.LLM_MAX_TOKEN_PER_REQUEST,
                )
            )
        ),
        doc="Token threshold for repo analysis summarization.",
    )

    LLM_FILE_ANALYSIS_TOKEN_THRESHOLD = EnvField(
        int,
        transform=lambda v, cfg: limit_token_threshold(
            v, 0.4, cfg.LLM_MAX_TOKEN_PER_MINUTE, cfg.LLM_MAX_TOKEN_PER_REQUEST
        ),
        default_factory=lambda cfg: (
            cfg.DEFAULT_LLM_FILE_ANALYSIS_TOKEN_THRESHOLD
            or str(
                get_max_token_threshold(
                    0.4,
                    cfg.LLM_MAX_TOKEN_PER_MINUTE,
                    cfg.LLM_MAX_TOKEN_PER_REQUEST,
                )
            )
        ),
        doc="Token threshold for file analysis.",
    )
