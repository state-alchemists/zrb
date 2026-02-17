import asyncio
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
from prompt_toolkit.completion import CompleteEvent
from prompt_toolkit.document import Document

from zrb.llm.app.completion import InputCompleter
from zrb.llm.history_manager.any_history_manager import AnyHistoryManager


@pytest.fixture
def mock_history_manager():
    manager = MagicMock(spec=AnyHistoryManager)
    manager.search.return_value = ["session1", "session2"]
    return manager


@pytest.fixture
def completer(mock_history_manager):
    return InputCompleter(
        history_manager=mock_history_manager,
        attach_commands=["/attach"],
        exit_commands=["/exit"],
        info_commands=["/info"],
        save_commands=["/save"],
        load_commands=["/load"],
        redirect_output_commands=["/out"],
        summarize_commands=["/sum"],
    )


@pytest.fixture
def complete_event():
    return MagicMock(spec=CompleteEvent)


def test_command_completion(completer, complete_event):
    doc = Document(text="/ex", cursor_position=3)
    completions = list(completer.get_completions(doc, complete_event))
    assert any(c.text == "/exit" for c in completions)


@patch("zrb.llm.app.completion.datetime")
def test_save_completion(mock_datetime, completer, complete_event):
    mock_datetime.now.return_value = datetime(2023, 10, 27, 12, 30)
    mock_datetime.strftime = datetime.strftime

    doc = Document(text="/save ", cursor_position=6)
    completions = list(completer.get_completions(doc, complete_event))
    assert any(c.text == "2023-10-27-12-30" for c in completions)


@patch("zrb.llm.app.completion.datetime")
def test_redirect_completion(mock_datetime, completer, complete_event):
    mock_datetime.now.return_value = datetime(2023, 10, 27, 12, 30)

    doc = Document(text="/out ", cursor_position=5)
    completions = list(completer.get_completions(doc, complete_event))
    assert any(c.text == "2023-10-27-12-30.txt" for c in completions)


def test_load_completion(completer, complete_event):
    doc = Document(text="/load ", cursor_position=6)
    completions = list(completer.get_completions(doc, complete_event))
    assert any(c.text == "session1" for c in completions)
    assert any(c.text == "session2" for c in completions)


def test_different_prefix_completion(mock_history_manager, complete_event):
    completer = InputCompleter(
        history_manager=mock_history_manager,
        redirect_output_commands=[">out"],
    )
    doc = Document(text=">o", cursor_position=2)
    completions = list(completer.get_completions(doc, complete_event))
    assert any(c.text == ">out" for c in completions)


@pytest.mark.asyncio
async def test_file_completion_public_api(completer, complete_event):
    """Test public file completion behavior via get_completions."""
    with patch("os.walk") as mock_os_walk:
        # Simulate a file system with a few files and directories
        mock_os_walk.return_value = [
            (".", ["dir1", "dir2"], ["file1.txt", "file2.py"]),
            ("dir1", [], ["nested_file.md"]),
            ("dir2", ["sub_dir"], []),
            ("dir2/sub_dir", [], ["another.txt"]),
        ]

        # Test completion for "@f"
        doc = Document(text="@f", cursor_position=2)
        completions = list(completer.get_completions(doc, complete_event))
        assert any(c.text == "file1.txt" for c in completions)
        assert any(c.text == "file2.py" for c in completions)
        assert not any(
            c.text == "dir1/" for c in completions
        )  # Directories should not be completed when only files are expected

        # Test completion for "@dir1/"
        doc = Document(text="@dir1/", cursor_position=6)
        completions = list(completer.get_completions(doc, complete_event))
        assert any(c.text == "dir1/nested_file.md" for c in completions)

        # Test completion for "/attach f"
        doc = Document(text="/attach f", cursor_position=9)
        completions = list(completer.get_completions(doc, complete_event))
        assert any(c.text == "file1.txt" for c in completions)
        assert any(c.text == "file2.py" for c in completions)
        assert not any(
            c.text == "dir1/" for c in completions
        )  # Directories should not be completed for attach command

        # Test completion for "/attach dir2/sub_dir/"
        doc = Document(text="/attach dir2/sub_dir/", cursor_position=21)
        completions = list(completer.get_completions(doc, complete_event))
        assert any(c.text == "dir2/sub_dir/another.txt" for c in completions)
