"""LLM content: history, snapshot, journal dirs, summarization thresholds, file read limits."""

from __future__ import annotations

import os

from zrb.config.helper import (
    get_env,
    get_max_token_threshold,
    limit_token_threshold,
)
from zrb.util.string.conversion import to_boolean


class LLMContentMixin:
    def __init__(self):
        self.DEFAULT_LLM_HISTORY_DIR: str = ""
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

    def _get_max_threshold(self, factor: float) -> int:
        return get_max_token_threshold(
            factor, self.LLM_MAX_TOKEN_PER_MINUTE, self.LLM_MAX_TOKEN_PER_REQUEST
        )

    @property
    def LLM_HISTORY_DIR(self) -> str:
        default = self.DEFAULT_LLM_HISTORY_DIR
        if default == "":
            default = os.path.expanduser(
                os.path.join("~", f".{self.ROOT_GROUP_NAME}", "llm-history")
            )
        return get_env("LLM_HISTORY_DIR", default, self.ENV_PREFIX)

    @LLM_HISTORY_DIR.setter
    def LLM_HISTORY_DIR(self, value: str):
        os.environ[f"{self.ENV_PREFIX}_LLM_HISTORY_DIR"] = value

    @property
    def LLM_ENABLE_REWIND(self) -> bool:
        return to_boolean(
            get_env(
                "LLM_ENABLE_REWIND", self.DEFAULT_LLM_ENABLE_REWIND, self.ENV_PREFIX
            )
        )

    @LLM_ENABLE_REWIND.setter
    def LLM_ENABLE_REWIND(self, value: bool):
        os.environ[f"{self.ENV_PREFIX}_LLM_ENABLE_REWIND"] = "on" if value else "off"

    @property
    def LLM_SNAPSHOT_DIR(self) -> str:
        default = self.DEFAULT_LLM_SNAPSHOT_DIR
        if default == "":
            default = os.path.expanduser(
                os.path.join("~", f".{self.ROOT_GROUP_NAME}", "llm-snapshots")
            )
        return get_env("LLM_SNAPSHOT_DIR", default, self.ENV_PREFIX)

    @LLM_SNAPSHOT_DIR.setter
    def LLM_SNAPSHOT_DIR(self, value: str):
        os.environ[f"{self.ENV_PREFIX}_LLM_SNAPSHOT_DIR"] = value

    @property
    def LLM_JOURNAL_DIR(self) -> str:
        default = self.DEFAULT_LLM_JOURNAL_DIR
        if default == "":
            default = os.path.expanduser(
                os.path.join("~", f".{self.ROOT_GROUP_NAME}", "llm-notes")
            )
        return get_env("LLM_JOURNAL_DIR", default, self.ENV_PREFIX)

    @LLM_JOURNAL_DIR.setter
    def LLM_JOURNAL_DIR(self, value: str):
        os.environ[f"{self.ENV_PREFIX}_LLM_JOURNAL_DIR"] = value

    @property
    def LLM_JOURNAL_INDEX_FILE(self) -> str:
        return get_env(
            "LLM_JOURNAL_INDEX_FILE",
            self.DEFAULT_LLM_JOURNAL_INDEX_FILE,
            self.ENV_PREFIX,
        )

    @LLM_JOURNAL_INDEX_FILE.setter
    def LLM_JOURNAL_INDEX_FILE(self, value: str):
        os.environ[f"{self.ENV_PREFIX}_LLM_JOURNAL_INDEX_FILE"] = value

    @property
    def LLM_HISTORY_SUMMARIZATION_WINDOW(self) -> int:
        return int(
            get_env(
                "LLM_HISTORY_SUMMARIZATION_WINDOW",
                self.DEFAULT_LLM_HISTORY_SUMMARIZATION_WINDOW,
                self.ENV_PREFIX,
            )
        )

    @LLM_HISTORY_SUMMARIZATION_WINDOW.setter
    def LLM_HISTORY_SUMMARIZATION_WINDOW(self, value: int):
        os.environ[f"{self.ENV_PREFIX}_LLM_HISTORY_SUMMARIZATION_WINDOW"] = str(value)

    @property
    def LLM_CONVERSATIONAL_SUMMARIZATION_TOKEN_THRESHOLD(self) -> int:
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
    def LLM_CONVERSATIONAL_SUMMARIZATION_TOKEN_THRESHOLD(self, value: int):
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
    def LLM_MESSAGE_SUMMARIZATION_TOKEN_THRESHOLD(self, value: int):
        os.environ[f"{self.ENV_PREFIX}_LLM_MESSAGE_SUMMARIZATION_TOKEN_THRESHOLD"] = (
            str(value)
        )

    @property
    def LLM_REPO_ANALYSIS_EXTRACTION_TOKEN_THRESHOLD(self) -> int:
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
    def LLM_REPO_ANALYSIS_EXTRACTION_TOKEN_THRESHOLD(self, value: int):
        os.environ[
            f"{self.ENV_PREFIX}_LLM_REPO_ANALYSIS_EXTRACTION_TOKEN_THRESHOLD"
        ] = str(value)

    @property
    def LLM_REPO_ANALYSIS_SUMMARIZATION_TOKEN_THRESHOLD(self) -> int:
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
    def LLM_REPO_ANALYSIS_SUMMARIZATION_TOKEN_THRESHOLD(self, value: int):
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
    def LLM_FILE_ANALYSIS_TOKEN_THRESHOLD(self, value: int):
        os.environ[f"{self.ENV_PREFIX}_LLM_FILE_ANALYSIS_TOKEN_THRESHOLD"] = str(value)

    @property
    def LLM_HISTORY_MAX_DISPLAY_CHARS(self) -> int:
        """Maximum characters to display in history."""
        return int(
            get_env(
                "LLM_HISTORY_MAX_DISPLAY_CHARS",
                self.DEFAULT_LLM_HISTORY_MAX_DISPLAY_CHARS,
                self.ENV_PREFIX,
            )
        )

    @LLM_HISTORY_MAX_DISPLAY_CHARS.setter
    def LLM_HISTORY_MAX_DISPLAY_CHARS(self, value: int):
        os.environ[f"{self.ENV_PREFIX}_LLM_HISTORY_MAX_DISPLAY_CHARS"] = str(value)

    @property
    def LLM_HISTORY_TRUNCATE_LENGTH(self) -> int:
        """Character length for history truncation."""
        return int(
            get_env(
                "LLM_HISTORY_TRUNCATE_LENGTH",
                self.DEFAULT_LLM_HISTORY_TRUNCATE_LENGTH,
                self.ENV_PREFIX,
            )
        )

    @LLM_HISTORY_TRUNCATE_LENGTH.setter
    def LLM_HISTORY_TRUNCATE_LENGTH(self, value: int):
        os.environ[f"{self.ENV_PREFIX}_LLM_HISTORY_TRUNCATE_LENGTH"] = str(value)

    @property
    def LLM_FILE_READ_LINES(self) -> int:
        """Default number of lines to read from files (head/tail)."""
        return int(
            get_env(
                "LLM_FILE_READ_LINES",
                self.DEFAULT_LLM_FILE_READ_LINES,
                self.ENV_PREFIX,
            )
        )

    @LLM_FILE_READ_LINES.setter
    def LLM_FILE_READ_LINES(self, value: int):
        os.environ[f"{self.ENV_PREFIX}_LLM_FILE_READ_LINES"] = str(value)
