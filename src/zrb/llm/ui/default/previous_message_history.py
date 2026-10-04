"""Persistent previous-message history for the default TUI's input box.

The input box's Up/Down recall walks two sources, newest first: the user
messages of the conversation just loaded with `/load` (seeded on load), then
the cross-session history of every message the user has submitted before,
persisted under `CFG.LLM_PREVIOUS_MESSAGE_HISTORY_DIR`.

`PreviousMessageHistory` is a prompt_toolkit `History` so the input buffer's
own `append_to_history` (the submit path) stores each submitted message here
without extra wiring; recall navigation itself lives in `UIMessageEditing`,
which reads `recall_strings()`.
"""

from __future__ import annotations

import json
import os

from prompt_toolkit.history import History


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
        self._trim()
        self._write_persistent()

    # -- persistence --------------------------------------------------------

    def _history_file(self) -> str:
        return os.path.join(self._history_dir, "previous-messages.json")

    def _read_persistent(self) -> list[str]:
        try:
            with open(self._history_file(), encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            return []
        if not isinstance(data, list):
            return []
        return [str(item) for item in data]

    def _write_persistent(self) -> None:
        os.makedirs(self._history_dir, exist_ok=True)
        tmp_path = f"{self._history_file()}.tmp"
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(self._persistent, f, ensure_ascii=False)
            os.replace(tmp_path, self._history_file())
        except OSError:
            try:
                os.remove(tmp_path)
            except OSError:
                pass

    def _trim(self) -> None:
        if self._max_entries > 0 and len(self._persistent) > self._max_entries:
            del self._persistent[self._max_entries:]
