"""LLM content: history, snapshot, journal dirs, summarization thresholds, file read limits."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from zrb.config.env_field import EnvField, on_off
from zrb.config.helper import (
    get_env,
    get_max_token_threshold,
    limit_token_threshold,
)
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

    def _get_max_threshold(self, factor: float) -> int:
        return get_max_token_threshold(
            factor, self.LLM_MAX_TOKEN_PER_MINUTE, self.LLM_MAX_TOKEN_PER_REQUEST
        )

    def _safe_int_from_env(self, key: str, default: str) -> int:
        """Read an env var as int, falling back to *default* if unset or unparseable."""
        try:
            return int(get_env(key, default, self.ENV_PREFIX))
        except (ValueError, TypeError):
            try:
                return int(default)
            except (ValueError, TypeError):
                return 0

    @property
    def LLM_HISTORY_BACKUP_RETAIN(self) -> int:
        """Number of timestamped history backups to keep per conversation.

        ``0`` disables backup writes entirely. ``-1`` keeps every backup
        (legacy behavior). The default keeps the most recent few so a
        long-running install does not accumulate one file per turn forever.
        """
        return self._safe_int_from_env(
            "LLM_HISTORY_BACKUP_RETAIN",
            self.DEFAULT_LLM_HISTORY_BACKUP_RETAIN,
        )

    @LLM_HISTORY_BACKUP_RETAIN.setter
    def LLM_HISTORY_BACKUP_RETAIN(self, value: int) -> None:
        os.environ[f"{self.ENV_PREFIX}_LLM_HISTORY_BACKUP_RETAIN"] = str(value)

    @property
    def LLM_HISTORY_SUMMARIZATION_WINDOW(self) -> int:
        return self._safe_int_from_env(
            "LLM_HISTORY_SUMMARIZATION_WINDOW",
            self.DEFAULT_LLM_HISTORY_SUMMARIZATION_WINDOW,
        )

    @LLM_HISTORY_SUMMARIZATION_WINDOW.setter
    def LLM_HISTORY_SUMMARIZATION_WINDOW(self, value: int) -> None:
        os.environ[f"{self.ENV_PREFIX}_LLM_HISTORY_SUMMARIZATION_WINDOW"] = str(value)

    @property
    def LLM_CONVERSATIONAL_SUMMARIZATION_TOKEN_THRESHOLD(
        self,
    ) -> int:
        default = self.DEFAULT_LLM_CONVERSATIONAL_SUMMARIZATION_TOKEN_THRESHOLD
        if default == "":
            default = str(self._get_max_threshold(0.6))
        threshold = int(
            get_env(
                "LLM_CONVERSATIONAL_SUMMARIZATION_TOKEN_THRESHOLD",
                default,
                self.ENV_PREFIX,
            )
        )
        return limit_token_threshold(
            threshold,
            0.6,
            self.LLM_MAX_TOKEN_PER_MINUTE,
            self.LLM_MAX_TOKEN_PER_REQUEST,
        )

    @LLM_CONVERSATIONAL_SUMMARIZATION_TOKEN_THRESHOLD.setter
    def LLM_CONVERSATIONAL_SUMMARIZATION_TOKEN_THRESHOLD(self, value: int) -> None:
        os.environ[
            f"{self.ENV_PREFIX}_LLM_CONVERSATIONAL_SUMMARIZATION_TOKEN_THRESHOLD"
        ] = str(value)

    @property
    def LLM_MESSAGE_SUMMARIZATION_TOKEN_THRESHOLD(self) -> int:
        default = self.DEFAULT_LLM_MESSAGE_SUMMARIZATION_TOKEN_THRESHOLD
        if default == "":
            default = str(self.LLM_CONVERSATIONAL_SUMMARIZATION_TOKEN_THRESHOLD // 2)
        threshold = int(
            get_env(
                "LLM_MESSAGE_SUMMARIZATION_TOKEN_THRESHOLD",
                default,
                self.ENV_PREFIX,
            )
        )
        return limit_token_threshold(
            threshold,
            0.6,
            self.LLM_MAX_TOKEN_PER_MINUTE,
            self.LLM_MAX_TOKEN_PER_REQUEST,
        )

    @LLM_MESSAGE_SUMMARIZATION_TOKEN_THRESHOLD.setter
    def LLM_MESSAGE_SUMMARIZATION_TOKEN_THRESHOLD(self, value: int) -> None:
        os.environ[f"{self.ENV_PREFIX}_LLM_MESSAGE_SUMMARIZATION_TOKEN_THRESHOLD"] = (
            str(value)
        )

    @property
    def LLM_REPO_ANALYSIS_EXTRACTION_TOKEN_THRESHOLD(
        self,
    ) -> int:
        default = self.DEFAULT_LLM_REPO_ANALYSIS_EXTRACTION_TOKEN_THRESHOLD
        if default == "":
            default = str(self._get_max_threshold(0.4))
        threshold = int(
            get_env(
                "LLM_REPO_ANALYSIS_EXTRACTION_TOKEN_THRESHOLD",
                default,
                self.ENV_PREFIX,
            )
        )
        return limit_token_threshold(
            threshold,
            0.4,
            self.LLM_MAX_TOKEN_PER_MINUTE,
            self.LLM_MAX_TOKEN_PER_REQUEST,
        )

    @LLM_REPO_ANALYSIS_EXTRACTION_TOKEN_THRESHOLD.setter
    def LLM_REPO_ANALYSIS_EXTRACTION_TOKEN_THRESHOLD(self, value: int) -> None:
        os.environ[
            f"{self.ENV_PREFIX}_LLM_REPO_ANALYSIS_EXTRACTION_TOKEN_THRESHOLD"
        ] = str(value)

    @property
    def LLM_REPO_ANALYSIS_SUMMARIZATION_TOKEN_THRESHOLD(
        self,
    ) -> int:
        default = self.DEFAULT_LLM_REPO_ANALYSIS_SUMMARIZATION_TOKEN_THRESHOLD
        if default == "":
            default = str(self._get_max_threshold(0.4))
        threshold = int(
            get_env(
                "LLM_REPO_ANALYSIS_SUMMARIZATION_TOKEN_THRESHOLD",
                default,
                self.ENV_PREFIX,
            )
        )
        return limit_token_threshold(
            threshold,
            0.4,
            self.LLM_MAX_TOKEN_PER_MINUTE,
            self.LLM_MAX_TOKEN_PER_REQUEST,
        )

    @LLM_REPO_ANALYSIS_SUMMARIZATION_TOKEN_THRESHOLD.setter
    def LLM_REPO_ANALYSIS_SUMMARIZATION_TOKEN_THRESHOLD(self, value: int) -> None:
        os.environ[
            f"{self.ENV_PREFIX}_LLM_REPO_ANALYSIS_SUMMARIZATION_TOKEN_THRESHOLD"
        ] = str(value)

    @property
    def LLM_FILE_ANALYSIS_TOKEN_THRESHOLD(self) -> int:
        default = self.DEFAULT_LLM_FILE_ANALYSIS_TOKEN_THRESHOLD
        if default == "":
            default = str(self._get_max_threshold(0.4))
        threshold = int(
            get_env(
                "LLM_FILE_ANALYSIS_TOKEN_THRESHOLD",
                default,
                self.ENV_PREFIX,
            )
        )
        return limit_token_threshold(
            threshold,
            0.4,
            self.LLM_MAX_TOKEN_PER_MINUTE,
            self.LLM_MAX_TOKEN_PER_REQUEST,
        )

    @LLM_FILE_ANALYSIS_TOKEN_THRESHOLD.setter
    def LLM_FILE_ANALYSIS_TOKEN_THRESHOLD(self, value: int) -> None:
        os.environ[f"{self.ENV_PREFIX}_LLM_FILE_ANALYSIS_TOKEN_THRESHOLD"] = str(value)

    @property
    def LLM_HISTORY_MAX_DISPLAY_CHARS(self) -> int:
        """Maximum characters to display in history."""
        return self._safe_int_from_env(
            "LLM_HISTORY_MAX_DISPLAY_CHARS",
            self.DEFAULT_LLM_HISTORY_MAX_DISPLAY_CHARS,
        )

    @LLM_HISTORY_MAX_DISPLAY_CHARS.setter
    def LLM_HISTORY_MAX_DISPLAY_CHARS(self, value: int) -> None:
        os.environ[f"{self.ENV_PREFIX}_LLM_HISTORY_MAX_DISPLAY_CHARS"] = str(value)

    @property
    def LLM_HISTORY_TRUNCATE_LENGTH(self) -> int:
        """Character length for history truncation."""
        return self._safe_int_from_env(
            "LLM_HISTORY_TRUNCATE_LENGTH",
            self.DEFAULT_LLM_HISTORY_TRUNCATE_LENGTH,
        )

    @LLM_HISTORY_TRUNCATE_LENGTH.setter
    def LLM_HISTORY_TRUNCATE_LENGTH(self, value: int) -> None:
        os.environ[f"{self.ENV_PREFIX}_LLM_HISTORY_TRUNCATE_LENGTH"] = str(value)

    @property
    def LLM_FILE_READ_LINES(self) -> int:
        """Default number of lines to read from files (head/tail)."""
        return self._safe_int_from_env(
            "LLM_FILE_READ_LINES",
            self.DEFAULT_LLM_FILE_READ_LINES,
        )

    @LLM_FILE_READ_LINES.setter
    def LLM_FILE_READ_LINES(self, value: int) -> None:
        os.environ[f"{self.ENV_PREFIX}_LLM_FILE_READ_LINES"] = str(value)
