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
        self.DEFAULT_LLM_USAGE_DIR: str = ""
        self.DEFAULT_LLM_HISTORY_BACKUP_RETAIN: str = "3"
        self.DEFAULT_LLM_PREVIOUS_MESSAGE_HISTORY_DIR: str = ""
        self.DEFAULT_LLM_PREVIOUS_MESSAGE_HISTORY_MAX_ENTRIES: str = "1000"
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
        self.DEFAULT_LLM_ARCHIVE_LOCK_TIMEOUT: str = "30"
        self.DEFAULT_LLM_AUTO_NAME_ENABLED: str = "on"
        self.DEFAULT_LLM_JOURNAL_ENABLED: str = "on"
        self.DEFAULT_LLM_JOURNAL_DIR: str = ""
        self.DEFAULT_LLM_JOURNAL_INDEX_FILE: str = "index.md"
        self.DEFAULT_LLM_JOURNAL_INDEX_MAX_CHARS: str = "2500"
        self.DEFAULT_LLM_JOURNAL_CLAIMS_PER_TURN: str = "3"
        self.DEFAULT_LLM_JOURNAL_CLAIMS_MAX_CHARS: str = "1000"
        self.DEFAULT_LLM_JOURNAL_AUTO_SEARCH_ENABLED: str = "on"
        self.DEFAULT_LLM_JOURNAL_GIT_ENABLED: str = "on"
        self.DEFAULT_LLM_JOURNAL_COMPLIANCE_ENABLED: str = "on"
        self.DEFAULT_LLM_JOURNAL_LOCK_TIMEOUT: str = "30"
        self.DEFAULT_LLM_SELF_REVIEW_ENABLED: str = "off"
        self.DEFAULT_LLM_SELF_REVIEW_MAX_ROUNDS: str = "2"
        self.DEFAULT_LLM_SELF_REVIEW_MODEL: str = ""
        self.DEFAULT_LLM_SELF_REVIEW_TIMEOUT: str = "240"
        self.DEFAULT_LLM_SELF_REVIEW_MAX_TRACKED_TURNS: str = "64"
        self.DEFAULT_LLM_HISTORY_SUMMARIZATION_WINDOW: str = "300"
        self.DEFAULT_LLM_HISTORY_TAIL_BUDGET_RATIO: str = "0.4"
        self.DEFAULT_LLM_HISTORY_TAIL_MAX_TOKENS: str = "24000"
        self.DEFAULT_LLM_SUMMARY_MAX_TOKEN_RATIO: str = "0.05"
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

    LLM_USAGE_DIR = EnvField(
        str,
        default_factory=lambda cfg: (
            cfg.DEFAULT_LLM_USAGE_DIR
            if cfg.DEFAULT_LLM_USAGE_DIR
            else os.path.expanduser(
                os.path.join("~", f".{cfg.ROOT_GROUP_NAME}", "llm-usage")
            )
        ),
        doc=(
            "Directory for the local LLM usage logs: `usage-YYYY-MM.jsonl` holds "
            "one JSON line per completed run (token counts, request and "
            "tool-call counts, per-tool call and error counts by tool name, the "
            "run's duration and its cost when the model is priced), and "
            "`journal-YYYY-MM.jsonl` holds one line per journal event (index "
            "injected, searched, read, written, superseded, deleted) with note "
            "ids stored as short hashes. Numbers, tool names and hashed ids only "
            "— no prompt text, tool arguments, note titles or file content — "
            "which is what lets `/usage` work without an opt-in."
        ),
    )

    LLM_PREVIOUS_MESSAGE_HISTORY_DIR = EnvField(
        str,
        default_factory=lambda cfg: (
            cfg.DEFAULT_LLM_PREVIOUS_MESSAGE_HISTORY_DIR
            if cfg.DEFAULT_LLM_PREVIOUS_MESSAGE_HISTORY_DIR
            else os.path.expanduser(
                os.path.join(
                    "~", f".{cfg.ROOT_GROUP_NAME}", "llm-previous-message-history"
                )
            )
        ),
        doc=(
            "Directory for the cross-session previous-message history the chat "
            "input box recalls with Up/Down. Holds one file of the user "
            "messages submitted across every session."
        ),
    )

    LLM_PREVIOUS_MESSAGE_HISTORY_MAX_ENTRIES = EnvField(
        int,
        fallback=0,
        doc=(
            "Maximum previous user messages kept in the cross-session input "
            "history. Older entries are dropped first. 0 keeps every entry."
        ),
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

    LLM_AUTO_NAME_ENABLED = EnvField(
        to_boolean,
        serialize=on_off,
        doc=(
            "Rename a conversation that still has its generated name, after "
            "its first message, to `<generated-name>-<topic>` using the small "
            "model. A name you chose is never renamed."
        ),
    )

    LLM_AUTO_NAME_MODEL = EnvField(
        str,
        doc=(
            "Model that names a conversation. Empty uses the small model "
            "({ENV_PREFIX}_LLM_SMALL_MODEL, else the main model)."
        ),
    )

    LLM_JOURNAL_ENABLED = EnvField(
        to_boolean,
        serialize=on_off,
        doc=(
            "Master switch for the cross-session journal. Off unregisters the "
            "five journal tools (SearchJournal, LogActivity, "
            "WriteJournalNote, SupersedeJournalNote, DeleteJournalNote) and "
            "suppresses the "
            "<journal-index> injection. Those tools are the whole interface — "
            "there is no prompt section describing a journal protocol — so off "
            "means the model is never told a journal exists, and neither reads "
            "nor writes one. LLM_JOURNAL_DIR has no 'unset' value that achieves "
            "this (it falls back to ~/<root>/llm-notes), which is why this knob "
            "exists."
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
        doc=(
            "Filename of every journal index: the one at the journal root — "
            "the index injected into context — and one in each category and "
            "activity-log directory. The reader and every writer resolve it "
            "from here. Set it before the first write: an existing journal "
            "keeps the indexes it already has under their old name, so a "
            "changed value starts fresh indexes rather than renaming the old "
            "ones."
        ),
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
            "Constraints, Agent, Recent). Oldest unpinned entries are evicted "
            "first so a stale headline does not sit in the always-injected "
            "index forever; a pinned entry goes only when the whole section is "
            "pinned. `<= 0` disables the cap (uncapped)."
        ),
    )

    LLM_JOURNAL_CATALOG_MAX_ENTRIES = EnvField(
        int,
        fallback=25,
        doc=(
            "Maximum notes the root index's `## Recent Insights` catalog lists "
            "(a count, not a duration). The newest active notes by `updated` "
            "are shown, newest first, followed by one line counting the older "
            "ones; the category indexes always list every note. `<= 0` lists "
            "every active note (uncapped)."
        ),
    )

    LLM_JOURNAL_CLAIMS_PER_TURN = EnvField(
        int,
        fallback=3,
        doc=(
            "Maximum journal claims injected into a turn after the first one "
            "(a count). The index goes in once, at the start of a session, so a "
            "note written later is invisible until the conversation is "
            "compacted; each turn then shows the highest-scoring claims the "
            "session has not been shown yet — pinned ones first, then the "
            "freshest, then those sharing a word with the message. `<= 0` "
            "suppresses the mid-session claims entirely."
        ),
    )

    LLM_JOURNAL_CLAIMS_MAX_CHARS = EnvField(
        int,
        fallback=1000,
        doc=(
            "Maximum characters of those claims in one turn — a second budget "
            "beside LLM_JOURNAL_CLAIMS_PER_TURN, so one long claim cannot spend "
            "the whole allowance. A claim whose line does not fit is skipped. "
            "`<= 0` suppresses the mid-session claims entirely."
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
            "commit after every LogActivity/WriteJournalNote/"
            "SupersedeJournalNote/DeleteJournalNote "
            "call. Gives the journal unbounded, diffable history and makes a "
            "delete or a bad overwrite recoverable by a human outside the "
            "tools (the in-file History block only keeps the last 3 "
            "revisions). Best-effort: a missing `git` binary or a failed "
            "commit never breaks journaling, it just forgoes the commit."
        ),
    )

    LLM_JOURNAL_COMPLIANCE_TURNS = EnvField(
        int,
        fallback=12,
        doc=(
            "User turns between journal-compliance checks on a conversation that "
            "wrote no files and stated no preference. The judge otherwise runs only "
            "on a turn that did one of those, which a long conversation touching no "
            "file never does; every this many turns it reads the transcript and "
            "decides for itself. `<= 0` turns the periodic check off."
        ),
    )

    LLM_JOURNAL_COMPLIANCE_ENABLED = EnvField(
        to_boolean,
        serialize=on_off,
        doc=(
            "Register the built-in `journal-compliance-judge` Stop hook, which "
            "asks a small model whether a turn that wrote files or stated a "
            "preference left the journal recording it. On by default; "
            "`LLM_JOURNAL_ENABLED=off` still takes it out with the rest of "
            "journaling."
        ),
    )

    LLM_JOURNAL_LOCK_TIMEOUT = EnvField(
        float,
        doc=(
            "Seconds a journal write waits for another writer's root lock before "
            "failing with a busy-journal error. Zero or negative fails immediately."
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

    LLM_AGENT_MESSAGE_LIMIT = EnvField(
        int,
        fallback=20,
        doc=(
            "Maximum messages the main agent and one delegated sub-agent may "
            "send each other (both directions together) before the send "
            "tools refuse, so two agents cannot answer each other forever. "
            "Human messages do not count."
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

    LLM_ARCHIVE_LOCK_TIMEOUT = EnvField(
        float,
        doc=(
            "Seconds a verbatim archive append waits for another writer before "
            "returning no archive pointer. Zero or negative fails immediately."
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
        doc=(
            "Most messages kept verbatim after summarization. A backstop for "
            "histories of many small messages: token pressure is what normally "
            "triggers summarization and bounds the kept tail."
        ),
    )

    LLM_HISTORY_TAIL_BUDGET_RATIO = EnvField(
        float,
        fallback=0.4,
        doc=(
            "Share of the summarization threshold the verbatim tail may fill: "
            "the newest messages that fit it are kept word for word instead of "
            "being summarized, so the rest of the window remains for the "
            "conversation that follows. 0.4 is 150,000 tokens on a 500,000-token "
            "window. The ratio is a budget and not a target: the split usually "
            "keeps less, because it prefers a turn boundary and the message "
            "window caps the count. Values outside 0.05-0.8 are clamped, since 0 "
            "would keep no recent conversation at all and a tail filling the "
            "threshold would make a compaction free nothing. See "
            "LLM_HISTORY_TAIL_MAX_TOKENS for the absolute ceiling that applies "
            "whichever of the two is smaller."
        ),
    )

    LLM_HISTORY_TAIL_MAX_TOKENS = EnvField(
        int,
        fallback=24_000,
        doc=(
            "Absolute ceiling on the verbatim tail, in tokens, applied on top of "
            "LLM_HISTORY_TAIL_BUDGET_RATIO: whichever is smaller wins. A share of "
            "a large window is still a lot of transcript — on a 500,000-token "
            "window the 0.4 ratio alone allows 150,000 tokens, roughly twenty "
            "times the room a summary gets for saying what the work was — and the "
            "next turn re-reads every one of them. The tail is a handover, not "
            "evidence: the messages it replaces are archived in full. 0 disables "
            "the ceiling and leaves the ratio in charge."
        ),
    )

    LLM_SUMMARY_MAX_TOKEN_RATIO = EnvField(
        float,
        fallback=0.0,
        doc=(
            "Share of the summarization threshold one summary may fill, so the "
            "bound scales with the model's window instead of fixing a token "
            "count: 0.05 is 18,750 tokens on a 500,000-token window and the "
            "floor below that. A summary over the cap is shortened before it "
            "replaces the history; 0 disables the cap."
        ),
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
            v, 0.75, cfg.LLM_MAX_TOKEN_PER_MINUTE, cfg.LLM_MAX_TOKEN_PER_REQUEST
        ),
        default_factory=lambda cfg: (
            cfg.DEFAULT_LLM_CONVERSATIONAL_SUMMARIZATION_TOKEN_THRESHOLD
            or str(
                get_max_token_threshold(
                    0.75,
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
