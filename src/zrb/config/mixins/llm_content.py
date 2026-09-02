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
        self.DEFAULT_LLM_JOURNAL_ENABLED: str = "on"
        self.DEFAULT_LLM_JOURNAL_DIR: str = ""
        self.DEFAULT_LLM_JOURNAL_INDEX_FILE: str = "index.md"
        self.DEFAULT_LLM_JOURNAL_INDEX_MAX_CHARS: str = "2500"
        self.DEFAULT_LLM_JOURNAL_AUTO_SEARCH_ENABLED: str = "on"
        self.DEFAULT_LLM_JOURNAL_GIT_ENABLED: str = "on"
        self.DEFAULT_LLM_HISTORY_SUMMARIZATION_WINDOW: str = "100"
        self.DEFAULT_LLM_CONVERSATIONAL_SUMMARIZATION_TOKEN_THRESHOLD: str = ""
        self.DEFAULT_LLM_MESSAGE_SUMMARIZATION_TOKEN_THRESHOLD: str = ""
        self.DEFAULT_LLM_REPO_ANALYSIS_EXTRACTION_TOKEN_THRESHOLD: str = ""
        self.DEFAULT_LLM_REPO_ANALYSIS_SUMMARIZATION_TOKEN_THRESHOLD: str = ""
        self.DEFAULT_LLM_FILE_ANALYSIS_TOKEN_THRESHOLD: str = ""
        self.DEFAULT_LLM_HISTORY_MAX_DISPLAY_CHARS: str = "5000"
        self.DEFAULT_LLM_HISTORY_TRUNCATE_LENGTH: str = "100"
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

    LLM_JOURNAL_ENABLED = EnvField(
        to_boolean,
        serialize=on_off,
        doc=(
            "Master switch for the cross-session journal. Off unregisters the "
            "three journal tools (SearchJournal, LogActivity, "
            "WriteJournalNote) and suppresses the <journal-index> injection. "
            "Those tools are the whole interface — there is no prompt section "
            "describing a journal protocol — so off means the model is never "
            "told a journal exists, and neither reads nor writes one. "
            "LLM_JOURNAL_DIR has no 'unset' value that achieves this (it falls "
            "back to ~/<root>/llm-notes), which is why this knob exists."
        ),
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
        doc="Filename of the journal index file.",
    )

    LLM_JOURNAL_INDEX_MAX_CHARS = EnvField(
        int,
        fallback=0,
        doc=(
            "Maximum characters of the journal index injected into context. "
            "The index is the HUD — it carries the user's identity and standing "
            "preferences, so overflow is dropped from the end and the file is "
            "ordered most-durable-first. 0 suppresses the injection entirely; "
            "a negative value injects the whole index uncapped."
        ),
    )

    LLM_JOURNAL_HUD_MAX_ENTRIES_PER_SECTION = EnvField(
        int,
        fallback=20,
        doc=(
            "Maximum hud_line entries kept per root-index HUD section (User, "
            "Preferences, Active Constraints). Oldest entries are evicted first "
            "so a stale preference does not sit in the always-injected index "
            "forever. `<= 0` disables the cap (uncapped, matching the old "
            "behavior)."
        ),
    )

    LLM_JOURNAL_AUTO_SEARCH_ENABLED = EnvField(
        to_boolean,
        serialize=on_off,
        doc=(
            "Run one SearchJournal against the opening message on a session's "
            "first turn, folding any hits into the injected <journal-index> "
            "block under a clearly separate, unverified 'Possibly Related' "
            "section. Costs one extra search subprocess, once per session."
        ),
    )

    LLM_JOURNAL_AUTO_SEARCH_MAX_HITS = EnvField(
        int,
        fallback=3,
        doc="Maximum SearchJournal hits folded into the first-turn auto-search.",
    )

    LLM_JOURNAL_GIT_ENABLED = EnvField(
        to_boolean,
        serialize=on_off,
        doc=(
            "Git-back the journal directory: `git init` it on first use, and "
            "commit after every LogActivity/WriteJournalNote/DeleteJournalNote "
            "call. Gives the journal unbounded, diffable history and makes a "
            "delete or a bad overwrite recoverable by a human outside the "
            "tools (the in-file History block only keeps the last 3 "
            "revisions). Best-effort: a missing `git` binary or a failed "
            "commit never breaks journaling, it just forgoes the commit."
        ),
    )

    LLM_ENABLE_REWIND = EnvField(
        to_boolean,
        serialize=on_off,
        doc="Enable/disable the rewind feature for LLM conversations.",
    )

    LLM_SUBAGENT_HISTORY_RETAIN = EnvField(
        int,
        fallback=50,
        doc=(
            "Maximum number of persisted delegated sub-agent sessions to keep "
            "on disk across all agent types; the oldest are pruned on each "
            "new one. Unlike ordinary conversations, each delegation writes a "
            "session under a brand-new, never-reused name, so nothing else "
            "bounds this — leaving it uncapped fills the disk over a "
            "long-running or heavily-delegating session. -1 keeps every one "
            "(only if you are certain you want that)."
        ),
    )

    LLM_HISTORY_BACKUP_RETAIN = EnvField(
        int,
        fallback=0,
        doc=(
            "Number of timestamped history backups to keep per conversation. "
            "0 disables backup writes entirely. -1 keeps every backup."
        ),
    )

    LLM_HISTORY_SUMMARIZATION_WINDOW = EnvField(
        int,
        fallback=0,
        doc="Number of turns before summarization is triggered.",
    )

    LLM_HISTORY_MAX_DISPLAY_CHARS = EnvField(
        int,
        fallback=0,
        doc="Maximum characters to display in history.",
    )

    LLM_HISTORY_TRUNCATE_LENGTH = EnvField(
        int,
        fallback=0,
        doc="Character length for history truncation.",
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
