
import pytest
from datetime import datetime
from unittest.mock import MagicMock, patch

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

def test_file_completion_at(completer, complete_event):
    # We need to mock _get_recursive_files or similar
    with patch.object(completer, "_get_recursive_files") as mock_files:
        mock_files.return_value = ["foo.py", "bar/baz.py"]
        
        doc = Document(text="@fo", cursor_position=3)
        completions = list(completer.get_completions(doc, complete_event))
        assert any(c.text == "foo.py" for c in completions)

def test_attach_completion(completer, complete_event):
    with patch.object(completer, "_get_recursive_files") as mock_files:
        mock_files.return_value = ["foo.py", "bar/baz.py", "ignored_dir/"]
        
        doc = Document(text="/attach ba", cursor_position=10)
        completions = list(completer.get_completions(doc, complete_event))
        assert any(c.text == "bar/baz.py" for c in completions)

def test_different_prefix_completion(mock_history_manager, complete_event):
    completer = InputCompleter(
        history_manager=mock_history_manager,
        redirect_output_commands=[">out"],
    )
    doc = Document(text=">o", cursor_position=2)
    completions = list(completer.get_completions(doc, complete_event))
    assert any(c.text == ">out" for c in completions)
