"""Cross-session previous-message history and its recall navigation.

`PreviousMessageHistory` is a prompt_toolkit `History` that persists submitted
messages under `CFG.LLM_PREVIOUS_MESSAGE_HISTORY_DIR` and holds the loaded
conversation's user messages ahead of them. `UIMessageEditing` walks that list
with Up/Down once no still-queued message is left to recall, and `UI` seeds the
list from `/load` (via `replay_history`).
"""

import json
import threading
import time
from unittest.mock import MagicMock

from pydantic_ai.messages import ModelRequest, ModelResponse, TextPart, UserPromptPart

from zrb.config.config import CFG
from zrb.llm.ui.base.message_queue import MessageQueue, QueuedMessage
from zrb.llm.ui.default.message_editing import UIMessageEditing
from zrb.llm.ui.default.previous_message_history import PreviousMessageHistory
from zrb.llm.ui.default.ui import UI
from zrb.util.file_lock import hold_file_lock


class _RecallBuffer:
    def __init__(self, text: str = ""):
        self.text = text
        self.cursor_position = len(text)


class _RecallField:
    def __init__(self):
        self.buffer = _RecallBuffer()


class _RecallEvent:
    def __init__(self, buffer: _RecallBuffer):
        self.current_buffer = buffer


class _RecallUI:
    """Stand-in owner composing a real `UIMessageEditing` over a recall list."""

    def __init__(self, previous_messages: PreviousMessageHistory | None):
        self.previous_messages = previous_messages
        self._message_queue = MessageQueue()
        self.input_field = _RecallField()
        self._message_editing = UIMessageEditing(self)

    @property
    def effective_message_queue(self) -> MessageQueue:
        return self._message_queue

    def open_agent_picker(self) -> bool:
        return False

    def __getattr__(self, name):
        editing = self.__dict__.get("_message_editing")
        if editing is not None and hasattr(editing, name):
            return getattr(editing, name)
        raise AttributeError(name)


def _queued_entry(text: str) -> QueuedMessage:
    async def run():
        pass

    return QueuedMessage(text=text, attachments=[], kind="message", run=run)


def _hold_lock(path: str) -> tuple[threading.Thread, threading.Event]:
    """Hold `path`'s lock in a background thread until its release event is set."""
    held = threading.Event()
    release = threading.Event()

    def holder():
        with hold_file_lock(path):
            held.set()
            release.wait(5)

    thread = threading.Thread(target=holder)
    thread.start()
    held.wait(5)
    return thread, release


# --- PreviousMessageHistory --------------------------------------------------


class TestPreviousMessageHistory:
    def test_persists_across_instances(self, tmp_path):
        first = PreviousMessageHistory(history_dir=str(tmp_path))
        first.append_string("older")
        first.append_string("newer")

        second = PreviousMessageHistory(history_dir=str(tmp_path))
        assert second.recall_strings() == ["newer", "older"]

    def test_seed_precedes_persistent_newest_first(self, tmp_path):
        history = PreviousMessageHistory(history_dir=str(tmp_path))
        history.append_string("persisted")
        history.seed_conversation(["newest conversation", "older conversation"])

        assert history.recall_strings() == [
            "newest conversation",
            "older conversation",
            "persisted",
        ]

    def test_seed_replaces_previous_seed(self, tmp_path):
        history = PreviousMessageHistory(history_dir=str(tmp_path))
        history.seed_conversation(["old seed"])
        history.seed_conversation(["new seed"])

        assert history.recall_strings() == ["new seed"]

    def test_max_entries_caps_persistent_history(self, tmp_path):
        history = PreviousMessageHistory(history_dir=str(tmp_path), max_entries=2)
        history.append_string("a")
        history.append_string("b")
        history.append_string("c")

        assert history.recall_strings() == ["c", "b"]
        reloaded = PreviousMessageHistory(history_dir=str(tmp_path), max_entries=2)
        assert reloaded.recall_strings() == ["c", "b"]

    def test_corrupt_file_reads_as_empty(self, tmp_path):
        (tmp_path / "previous-messages.json").write_text("{not json")
        history = PreviousMessageHistory(history_dir=str(tmp_path))

        assert history.recall_strings() == []

    def test_non_utf8_file_reads_as_empty(self, tmp_path):
        (tmp_path / "previous-messages.json").write_bytes(b"\xff\xfe\x80")
        history = PreviousMessageHistory(history_dir=str(tmp_path))

        assert history.recall_strings() == []

    def test_unencodable_message_is_recorded_without_raising(self, tmp_path):
        """A message the UTF-8 write cannot encode (an unpaired surrogate) is
        best-effort: persistence fails silently and the in-memory entry stays
        recallable, so a chat turn never dies on a history write (PR #562
        round-3)."""
        history = PreviousMessageHistory(history_dir=str(tmp_path))
        text = "bad \ud800 surrogate"

        history.append_string(text)  # must not raise

        assert text in history.recall_strings()

    def test_max_entries_trims_oversized_file_on_load(self, tmp_path):
        (tmp_path / "previous-messages.json").write_text(
            json.dumps(["newest", "older", "oldest", "ancient"])
        )
        history = PreviousMessageHistory(history_dir=str(tmp_path), max_entries=2)

        assert history.recall_strings() == ["newest", "older"]
        # The on-disk file is conformed too, not just the in-memory copy.
        reloaded = PreviousMessageHistory(history_dir=str(tmp_path), max_entries=2)
        assert reloaded.recall_strings() == ["newest", "older"]

    def test_unwritable_history_directory_does_not_break_submission(self, tmp_path):
        # A regular file where the directory should be makes os.makedirs fail,
        # standing in for an unwritable directory without relying on
        # permission bits (which a root container would bypass).
        blocker = tmp_path / "blocker"
        blocker.write_text("")
        history = PreviousMessageHistory(history_dir=str(blocker / "subdir"))

        history.append_string("still remembered")

        assert history.recall_strings() == ["still remembered"]

    def test_two_sessions_do_not_clobber_each_other(self, tmp_path):
        # Both sessions load the same empty file, then each submits a message —
        # the second write must merge, not overwrite, the first's entry.
        first = PreviousMessageHistory(history_dir=str(tmp_path))
        second = PreviousMessageHistory(history_dir=str(tmp_path))

        first.append_string("from first")
        second.append_string("from second")

        reloaded = PreviousMessageHistory(history_dir=str(tmp_path))
        assert set(reloaded.recall_strings()) >= {"from first", "from second"}

    def test_submit_returns_promptly_when_lock_is_held(self, tmp_path):
        history = PreviousMessageHistory(history_dir=str(tmp_path))
        lock_file = str(tmp_path / "previous-messages.json.lock")
        thread, release = _hold_lock(lock_file)
        try:
            started = time.monotonic()
            history.append_string("held while locked")
            elapsed = time.monotonic() - started
        finally:
            release.set()
            thread.join()

        assert elapsed < 1.0
        assert history.recall_strings() == ["held while locked"]
        # The entry is still pending; a later write persists it once the lock
        # is free again.
        history.append_string("later")
        reloaded = PreviousMessageHistory(history_dir=str(tmp_path))
        assert set(reloaded.recall_strings()) >= {"held while locked", "later"}


# --- recall navigation through UIMessageEditing ------------------------------


class TestPreviousMessageRecall:
    def test_up_arrow_recalls_newest_previous_message_first(self, tmp_path):
        history = PreviousMessageHistory(history_dir=str(tmp_path))
        history.seed_conversation(["newest", "older"])
        ui = _RecallUI(previous_messages=history)
        buffer = ui.input_field.buffer
        buffer.text = "draft"
        buffer.cursor_position = len("draft")

        assert ui.handle_up_arrow(_RecallEvent(buffer)) is True
        assert buffer.text == "newest"

    def test_up_arrow_steps_older_then_swallows_at_oldest(self, tmp_path):
        history = PreviousMessageHistory(history_dir=str(tmp_path))
        history.seed_conversation(["newest", "older"])
        ui = _RecallUI(previous_messages=history)
        buffer = ui.input_field.buffer

        assert ui.handle_up_arrow(_RecallEvent(buffer)) is True
        assert buffer.text == "newest"
        assert ui.handle_up_arrow(_RecallEvent(buffer)) is True
        assert buffer.text == "older"
        # At the oldest message the key is consumed without changing the input.
        assert ui.handle_up_arrow(_RecallEvent(buffer)) is True
        assert buffer.text == "older"

    def test_down_arrow_steps_newer_then_restores_draft(self, tmp_path):
        history = PreviousMessageHistory(history_dir=str(tmp_path))
        history.seed_conversation(["newest", "older"])
        ui = _RecallUI(previous_messages=history)
        buffer = ui.input_field.buffer
        buffer.text = "draft"
        buffer.cursor_position = len("draft")

        ui.handle_up_arrow(_RecallEvent(buffer))  # "newest"
        ui.handle_up_arrow(_RecallEvent(buffer))  # "older"
        assert ui.handle_down_arrow(_RecallEvent(buffer)) is True
        assert buffer.text == "newest"
        assert ui.handle_down_arrow(_RecallEvent(buffer)) is True
        assert buffer.text == "draft"

    def test_up_arrow_prefers_queued_message_over_previous(self, tmp_path):
        history = PreviousMessageHistory(history_dir=str(tmp_path))
        history.seed_conversation(["previous message"])
        ui = _RecallUI(previous_messages=history)
        ui.effective_message_queue.put_nowait(_queued_entry("queued message"))
        buffer = ui.input_field.buffer

        assert ui.handle_up_arrow(_RecallEvent(buffer)) is True
        assert buffer.text == "queued message"

    def test_recall_navigation_active_during_previous_recall(self, tmp_path):
        history = PreviousMessageHistory(history_dir=str(tmp_path))
        history.seed_conversation(["previous message"])
        ui = _RecallUI(previous_messages=history)
        buffer = ui.input_field.buffer

        assert ui.recall_navigation_active() is False
        ui.handle_up_arrow(_RecallEvent(buffer))
        assert ui.recall_navigation_active() is True

    def test_no_previous_history_falls_through(self):
        ui = _RecallUI(previous_messages=None)
        buffer = ui.input_field.buffer

        assert ui.handle_up_arrow(_RecallEvent(buffer)) is False
        assert buffer.text == ""


# --- /load seeding through UI.replay_history ---------------------------------


class TestReplayHistorySeeding:
    def test_replay_history_seeds_user_messages(
        self, mock_ui_deps, tmp_path, monkeypatch
    ):
        monkeypatch.setattr(CFG, "LLM_PREVIOUS_MESSAGE_HISTORY_DIR", str(tmp_path))
        ui = UI(**mock_ui_deps)

        ui.replay_history([ModelRequest(parts=[UserPromptPart(content="hello")])])

        assert ui.previous_messages.recall_strings() == ["hello"]

    def test_replay_history_seeds_user_messages_newest_first(
        self, mock_ui_deps, tmp_path, monkeypatch
    ):
        monkeypatch.setattr(CFG, "LLM_PREVIOUS_MESSAGE_HISTORY_DIR", str(tmp_path))
        ui = UI(**mock_ui_deps)

        ui.replay_history(
            [
                ModelRequest(parts=[UserPromptPart(content="first")]),
                ModelResponse(parts=[TextPart(content="reply")]),
                ModelRequest(parts=[UserPromptPart(content="second")]),
            ]
        )

        assert ui.previous_messages.recall_strings() == ["second", "first"]


# --- submission recording at the common boundary -----------------------------


class TestSubmissionRecording:
    def test_non_utf8_file_does_not_block_ui_construction(
        self, mock_ui_deps, tmp_path, monkeypatch
    ):
        (tmp_path / "previous-messages.json").write_bytes(b"\xff\xfe\x80")
        monkeypatch.setattr(CFG, "LLM_PREVIOUS_MESSAGE_HISTORY_DIR", str(tmp_path))

        ui = UI(**mock_ui_deps)

        assert ui.previous_messages.recall_strings() == []

    def test_programmatic_submit_message_is_recorded(
        self, mock_ui_deps, tmp_path, monkeypatch
    ):
        monkeypatch.setattr(CFG, "LLM_PREVIOUS_MESSAGE_HISTORY_DIR", str(tmp_path))
        ui = UI(**mock_ui_deps)

        ui.submit_message("programmatic")

        assert ui.previous_messages.recall_strings() == ["programmatic"]

    def test_submit_user_message_is_recorded_once(
        self, mock_ui_deps, tmp_path, monkeypatch
    ):
        monkeypatch.setattr(CFG, "LLM_PREVIOUS_MESSAGE_HISTORY_DIR", str(tmp_path))
        ui = UI(**mock_ui_deps)

        ui.submit_user_message(ui.llm_task, "keyboard-style")

        assert ui.previous_messages.recall_strings() == ["keyboard-style"]

    def test_initial_message_is_recorded(self, mock_ui_deps, tmp_path, monkeypatch):
        monkeypatch.setattr(CFG, "LLM_PREVIOUS_MESSAGE_HISTORY_DIR", str(tmp_path))
        ui = UI(**mock_ui_deps, initial_message="hello")
        # `on_first_render` reads the deferred application's handler registry;
        # substitute a stub so the test never builds a real terminal app (and
        # `is_application_built` stays False, so the echo path asks the
        # terminal for its width the same way the other tests here do).
        monkeypatch.setattr(UI, "application", property(lambda self: MagicMock()))

        ui.on_first_render(None)

        assert ui.previous_messages.recall_strings() == ["hello"]
