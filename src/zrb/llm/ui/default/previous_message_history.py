"""Persistent previous-message history for the default TUI's input box.

The input box's Up/Down recall walks two sources, newest first: the user
messages of the conversation just loaded with `/load` (seeded on load), then
the cross-session history of every message the user has submitted before,
persisted under `CFG.LLM_PREVIOUS_MESSAGE_HISTORY_DIR`.

`PreviousMessageHistory` is a prompt_toolkit `History`, so `append_string`
keeps the input buffer's own bookkeeping in sync while `load_history_strings`
feeds its Up/Down recall. Recording happens at the common submit boundary
(`BaseUI.submit_user_message` → the default UI's `record_submitted_message`),
and recall navigation lives in `UIMessageEditing`, which reads
`recall_strings()`.

Persistence is best-effort, non-blocking, and concurrency-safe: each write
re-reads the file under an OS file lock, merges in the messages submitted this
session, trims to the configured limit, and atomically replaces the file via a
unique temporary name — so two concurrent sessions cannot clobber each other.
Submission writes take the lock without waiting: a write that finds it held
defers its messages to a later submission. Session teardown makes one short,
bounded retry, and a missing or unwritable history directory never breaks a
chat turn.
"""

from __future__ import annotations

import json
import os
import tempfile

from prompt_toolkit.history import History

from zrb.util.file_lock import FileLockTimeout, hold_file_lock

# A write takes the history lock or gives up at once — it never waits. A busy
# history directory must never stall the turn, so a write that cannot take the
# lock immediately leaves its entries in `_session_new` for the next write.
_LOCK_TIMEOUT_SECONDS = 0.0
# Session teardown may wait briefly for a contended lock so pending messages do
# not disappear when there is no later submission to retry them.
_TEARDOWN_LOCK_TIMEOUT_SECONDS = 0.25


class PreviousMessageHistory(History):
    """A `History` that persists submitted messages and holds a seeded
    conversation's user messages ahead of them.

    ``recall_strings()`` returns the combined recall list, newest first: the
    loaded conversation's user messages, then the cross-session history. The
    prompt_toolkit side (`load_history_strings`/`store_string`) keeps the same
    list visible to the input buffer's own history bookkeeping.
    """

    def __init__(self, history_dir: str, max_entries: int = 0) -> None:
        super().__init__()
        self._history_dir = os.path.expanduser(history_dir)
        self._max_entries = max_entries
        # The loaded conversation's user messages, newest first.
        self._seed: list[str] = []
        # Every submitted message, newest first, persisted to disk.
        self._persistent: list[str] = self._read_persistent()
        # Messages this session submitted but has not yet persisted.
        self._session_new: list[str] = []
        before = len(self._persistent)
        self._trim()
        if len(self._persistent) != before:
            # A file written under a larger (or no) limit: conform it on load.
            self._write_persistent()

    def seed_conversation(self, messages: list[str]) -> None:
        """Replace the loaded-conversation seed with *messages* (newest first)."""
        self._seed = list(messages)

    def recall_strings(self) -> list[str]:
        """The recall list, newest first: the loaded conversation, then the
        cross-session history."""
        return self._seed + self._persistent

    # -- prompt_toolkit History ---------------------------------------------

    def load_history_strings(self):
        """Yield the recall list newest first, as `History.load` expects."""
        yield from self._seed
        yield from self._persistent

    def store_string(self, string: str) -> None:
        """Persist one submitted message at the newest end."""
        self._persistent.insert(0, string)
        self._session_new.insert(0, string)
        self._trim()
        self._write_persistent()

    # -- persistence --------------------------------------------------------

    def _history_file(self) -> str:
        return os.path.join(self._history_dir, "previous-messages.json")

    def _lock_file(self) -> str:
        return os.path.join(self._history_dir, "previous-messages.json.lock")

    def _read_persistent(self) -> list[str]:
        try:
            with open(self._history_file(), encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError):
            # `JSONDecodeError` and `UnicodeDecodeError` are `ValueError`s. A
            # damaged history reads as empty rather than blocking startup.
            return []
        if not isinstance(data, list):
            return []
        return [str(item) for item in data]

    def _cap(self, entries: list[str]) -> list[str]:
        """The newest `_max_entries` of *entries* (all of them when unlimited)."""
        if self._max_entries > 0 and len(entries) > self._max_entries:
            return entries[: self._max_entries]
        return entries

    def _trim(self) -> None:
        """Drop entries past `_max_entries` from the in-memory list."""
        if self._max_entries > 0 and len(self._persistent) > self._max_entries:
            del self._persistent[self._max_entries :]

    def close(self) -> None:
        """Make one bounded attempt to persist messages pending at session end."""
        if self._session_new:
            self._write_persistent(timeout=_TEARDOWN_LOCK_TIMEOUT_SECONDS)

    def _write_persistent(self, timeout: float = _LOCK_TIMEOUT_SECONDS) -> None:
        """Persist the history, merging this session's new messages with disk.

        Never raises. When another session holds the lock the write is
        skipped and `_session_new` keeps the entries for the next write.
        """
        try:
            os.makedirs(self._history_dir, exist_ok=True)
        except OSError:
            return
        try:
            with hold_file_lock(self._lock_file(), timeout=timeout):
                disk = self._read_persistent()
                merged = self._cap(self._session_new + disk)
                self._write_file(merged)
                self._persistent = merged
                self._session_new = []
        except (OSError, UnicodeError, FileLockTimeout):
            # Keep `_session_new` so the messages are retried on a later write.
            # `UnicodeError` covers a submitted string the UTF-8 write cannot
            # encode (e.g. an unpaired surrogate): persistence is best-effort
            # and must never abort the chat turn.
            pass

    def _write_file(self, entries: list[str]) -> None:
        """Atomically write *entries* through a unique temporary file."""
        fd, tmp_path = tempfile.mkstemp(
            dir=self._history_dir, prefix="previous-messages-", suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(entries, f, ensure_ascii=False)
            os.replace(tmp_path, self._history_file())
        except (OSError, UnicodeError):
            try:
                os.remove(tmp_path)
            except OSError:
                pass
            raise
