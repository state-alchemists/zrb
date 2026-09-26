"""LLM content: history, snapshot, journal dirs, self-review, summarization thresholds, file read limits."""

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
        self.DEFAULT_LLM_ENABLE_REWIND: str = "on"
        self.DEFAULT_LLM_SNAPSHOT_DIR: str = ""
        self.DEFAULT_LLM_SNAPSHOT_RETENTION: str = "30d"
        self.DEFAULT_LLM_SNAPSHOT_FILE_MAX_MB: str = "50"
        self.DEFAULT_LLM_SNAPSHOT_LOOSE_MAX_FILES: str = "5000"
        self.DEFAULT_LLM_SNAPSHOT_LOOSE_MAX_MB: str = "200"
        self.DEFAULT_LLM_SNAPSHOT_COMMAND_TIMEOUT: str = "30"
        self.DEFAULT_LLM_SNAPSHOT_OPERATION_TIMEOUT: str = "120"
        self.DEFAULT_LLM_SNAPSHOT_LOCK_TIMEOUT: str = "60"
        self.DEFAULT_LLM_HISTORY_RETENTION: str = "30d"
        self.DEFAULT_LLM_JOURNAL_ENABLED: str = "on"
        self.DEFAULT_LLM_JOURNAL_DIR: str = ""
        self.DEFAULT_LLM_JOURNAL_INDEX_FILE: str = "index.md"
        self.DEFAULT_LLM_JOURNAL_INDEX_MAX_CHARS: str = "2500"
        self.DEFAULT_LLM_JOURNAL_AUTO_SEARCH_ENABLED: str = "on"
        self.DEFAULT_LLM_JOURNAL_GIT_ENABLED: str = "on"
        self.DEFAULT_LLM_SELF_REVIEW_ENABLED: str = "off"
        self.DEFAULT_LLM_SELF_REVIEW_MAX_ROUNDS: str = "2"
        self.DEFAULT_LLM_SELF_REVIEW_MODEL: str = ""
        self.DEFAULT_LLM_SELF_REVIEW_TIMEOUT: str = "240"
        self.DEFAULT_LLM_SELF_REVIEW_MAX_TRACKED_TURNS: str = "64"
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

    LLM_SNAPSHOT_RETENTION = EnvField(
        str,
        doc=(
            "How long a conversation's rewind history is kept after its newest "
            "snapshot (e.g. 30d, 2w); older histories are dropped, and their "
            "files pruned from the snapshot store, when a later session starts "
            "in the same directory. 0 keeps every history."
        ),
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
            "forever. `<= 0` disables the cap (uncapped)."
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

    LLM_SELF_REVIEW_ENABLED = EnvField(
        to_boolean,
        serialize=on_off,
        doc=(
            "Master switch for the built-in self-review Stop hook. On a turn "
            "that changed files, a reviewer agent with a fresh context reads "
            "the working directory's diff since the turn started — every "
            "repository under it, nested ones and worktrees included — and "
            "reports defects; findings extend the turn so the agent checks and "
            "fixes them before answering. Costs two snapshots per turn (at its "
            "start and at Stop) and one reviewer run per turn that changed "
            "files."
        ),
    )

    LLM_SELF_REVIEW_MAX_ROUNDS = EnvField(
        int,
        doc=(
            "Consecutive blocking reviews allowed. Each round that finds "
            "defects extends the turn once; after this many the turn ends. A "
            "review that lets the turn end resets the count."
        ),
    )

    LLM_SELF_REVIEW_MODEL = EnvField(
        str,
        doc=(
            "Model for the self-review reviewer. Empty uses the run's own "
            "model; a different model shares fewer of the author's blind spots."
        ),
    )

    LLM_SELF_REVIEW_TIMEOUT = EnvField(
        int,
        doc=(
            "Seconds one self-review may take. When it runs out the reviewer "
            "is cancelled — its model request included — and the turn ends "
            "unreviewed rather than waiting."
        ),
    )

    LLM_SELF_REVIEW_MAX_TRACKED_TURNS = EnvField(
        int,
        doc=(
            "Turns whose blocking-review count the self-review gate keeps at "
            "once. A turn that ends mid-continuation (cancelled, capped) never "
            "clears its count, so the oldest past this many are dropped; a "
            "dropped turn that does come back starts its count again."
        ),
    )

    LLM_ENABLE_REWIND = EnvField(
        to_boolean,
        serialize=on_off,
        doc=(
            "Snapshot the working directory before each turn so /rewind can "
            "restore it: every repository under it by its own .gitignore, and "
            "the files outside any repository up to LLM_SNAPSHOT_LOOSE_MAX_FILES "
            "/ LLM_SNAPSHOT_LOOSE_MAX_MB — past that, rewind is off for the "
            "session and says why. A file larger than LLM_SNAPSHOT_FILE_MAX_MB "
            "is left out, as if ignored: rewind neither restores nor removes it."
        ),
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

    LLM_SNAPSHOT_FILE_MAX_MB = EnvField(
        float,
        doc=(
            "A file larger than this many MB is left out of every snapshot — "
            "rewind's and the self-review gate's — as if ignored: rewind "
            "neither restores nor removes it, and self-review does not diff it."
        ),
    )

    LLM_SNAPSHOT_LOOSE_MAX_FILES = EnvField(
        int,
        doc=(
            "Most files a snapshot takes outside every git repository, where no "
            "ignore rule bounds it. Past it, rewind is off for the session and "
            "self-review falls back to the file tools' paths."
        ),
    )

    LLM_SNAPSHOT_LOOSE_MAX_MB = EnvField(
        float,
        doc=(
            "Most MB a snapshot takes outside every git repository; past it, the "
            "same as LLM_SNAPSHOT_LOOSE_MAX_FILES."
        ),
    )

    LLM_SNAPSHOT_COMMAND_TIMEOUT = EnvField(
        float,
        doc=(
            "Seconds one git command of a snapshot may take before it is killed. "
            "A rewind snapshot that runs out turns rewind off for the session."
        ),
    )

    LLM_SNAPSHOT_OPERATION_TIMEOUT = EnvField(
        float,
        doc=(
            "Seconds one rewind snapshot or restore may take as a whole, every "
            "git command in it included, once it holds the store; running out "
            "turns rewind off for the session."
        ),
    )

    LLM_SNAPSHOT_LOCK_TIMEOUT = EnvField(
        float,
        doc=(
            "Seconds a rewind snapshot or restore waits for another session's "
            "operation on the same directory before that one operation fails. "
            "Not counted against LLM_SNAPSHOT_OPERATION_TIMEOUT."
        ),
    )

    LLM_HISTORY_RETENTION = EnvField(
        str,
        doc=(
            "How long an auto-named conversation's history is kept after its "
            "last save (e.g. 30d, 2w), with its backups. A conversation you "
            "named — with /save, or a session name of your own — is kept "
            "forever; an auto-generated name (like bold-arch-1234) is what "
            "marks one as disposable. Pruned on the first save of each "
            "session. 0 keeps every history."
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
