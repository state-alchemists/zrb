"""Tests for `zrb.llm.task.chat.persistence`."""

from unittest.mock import MagicMock, patch

from zrb.attr.tpl import Tpl
from zrb.llm.history_manager.file_history_manager import FileHistoryManager
from zrb.llm.task.chat.persistence import (
    build_session_history_config,
    replay_conversation,
    resolve_history_manager,
)
from zrb.llm.task.history_config import HistoryConfig
from zrb.llm.ui.fallback.std_ui import StdUI


class _RecordingUI(StdUI):
    """A UI with no markdown step that records what it is asked to write."""

    def __init__(self):
        super().__init__()
        self.appended: list[str] = []

    def append_to_output(self, *values: object, **kwargs) -> None:
        self.appended.append("".join(str(value) for value in values))


def test_replay_conversation_uses_replay_history():
    """A UI that can replay history is asked to, and writes nothing else."""
    history_manager = MagicMock()
    history_manager.load.return_value = ["msg1", "msg2"]
    ui = MagicMock(spec=["replay_history", "append_to_output", "display"])
    ui.display = ui

    replay_conversation(ui, history_manager, "sess1")

    history_manager.load.assert_called_once_with("sess1")
    ui.replay_history.assert_called_once_with(["msg1", "msg2"])
    ui.append_to_output.assert_not_called()


def test_replay_conversation_falls_back_to_text_dump():
    """A UI that never implemented replay_history gets the formatted text."""
    history_manager = MagicMock()
    history_manager.load.return_value = ["msg1"]
    ui = _RecordingUI()

    with patch(
        "zrb.llm.util.history_formatter.format_history_as_text",
        return_value="FORMATTED",
    ):
        replay_conversation(ui, history_manager, "sess1")

    assert ui.appended == ["FORMATTED"]


def test_replay_conversation_empty_name_is_noop():
    """An empty conversation name never reaches the store."""
    history_manager = MagicMock()
    ui = MagicMock(spec=["replay_history", "append_to_output", "display"])
    ui.display = ui

    replay_conversation(ui, history_manager, "")

    history_manager.load.assert_not_called()
    ui.replay_history.assert_not_called()


def test_replay_conversation_missing_file_is_silent():
    """A session that is not on disk yet is not an error."""
    history_manager = MagicMock()
    history_manager.load.side_effect = FileNotFoundError("no such session")
    ui = MagicMock(spec=["replay_history", "append_to_output"])

    replay_conversation(ui, history_manager, "sess-missing")

    ui.replay_history.assert_not_called()


def test_replay_conversation_empty_history_writes_nothing():
    """An existing but empty conversation is not replayed."""
    history_manager = MagicMock()
    history_manager.load.return_value = []
    ui = MagicMock(spec=["replay_history", "append_to_output", "display"])
    ui.display = ui

    replay_conversation(ui, history_manager, "sess1")

    ui.replay_history.assert_not_called()


def test_resolve_history_manager_keeps_the_tasks_manager():
    """A task holding a manager hands that exact manager on."""
    manager = MagicMock()
    task = MagicMock()
    task.history_manager = manager

    assert resolve_history_manager(task) is manager


def test_resolve_history_manager_defaults_to_the_file_store():
    """A task that configured no manager gets the file-backed one."""
    task = MagicMock()
    task.history_manager = None

    assert isinstance(resolve_history_manager(task), FileHistoryManager)


def test_build_session_history_config_names_the_live_session():
    """The run's manager is used, and the name stays a per-request template."""
    manager = MagicMock()
    task = MagicMock()
    task.history_config = HistoryConfig()

    config = build_session_history_config(task, manager)

    assert config.history_manager is manager
    assert isinstance(config.conversation_name, Tpl)
