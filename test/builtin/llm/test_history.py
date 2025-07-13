import json
import os
from types import SimpleNamespace
from unittest import mock

import pytest

from zrb.builtin.llm import history as history_module
from zrb.task.llm.history import ConversationHistoryData


@pytest.fixture
def mock_shared_context():
    """Fixture for a mocked AnySharedContext."""
    context = mock.Mock()
    context.input = SimpleNamespace(start_new=False, previous_session=None)
    context.session = SimpleNamespace(name="current_session")
    context.log_warning = mock.Mock()
    context.log_error = mock.Mock()
    return context


@pytest.fixture(autouse=True)
def mock_llm_history_dir(monkeypatch, tmp_path):
    """Ensure LLM_HISTORY_DIR uses a temporary directory for tests."""
    llm_history_path = tmp_path / "test_llm_history"
    llm_history_path.mkdir(parents=True, exist_ok=True)
    temp_dir_str = str(llm_history_path)

    # Create a mock CFG object that has the desired LLM_HISTORY_DIR
    # and copy other attributes from the original CFG to keep other functionalities.
    original_cfg = history_module.CFG
    mock_cfg = mock.MagicMock(spec=original_cfg)

    # Copy attributes from original_cfg to mock_cfg
    # This ensures that other parts of CFG are still available if needed by the tests
    # and only LLM_HISTORY_DIR is overridden.
    for attr_name in dir(original_cfg):
        if not attr_name.startswith("__"):  # Exclude magic methods
            try:
                setattr(mock_cfg, attr_name, getattr(original_cfg, attr_name))
            except AttributeError:  # Some attributes might not be settable on MagicMock
                pass  # Or handle specific cases if necessary

    mock_cfg.LLM_HISTORY_DIR = temp_dir_str

    # Patch the CFG object within the history_module's scope
    monkeypatch.setattr(history_module, "CFG", mock_cfg)

    yield temp_dir_str
    # Pytest's tmp_path fixture handles cleanup of the temporary directory.


# --- Tests for read_chat_conversation ---


def test_read_chat_start_new(mock_shared_context):
    """Test read_chat_conversation returns None if start_new is True."""
    mock_shared_context.input.start_new = True
    result = history_module.read_chat_conversation(mock_shared_context)
    assert result is None


@mock.patch("zrb.builtin.llm.history.os.path.isfile")
@mock.patch("zrb.builtin.llm.history.read_file")
def test_read_chat_previous_session_exists(
    mock_read_file, mock_isfile, mock_shared_context, mock_llm_history_dir
):
    """Test reading history with a valid previous_session."""
    session_name = "prev_session"
    mock_shared_context.input.previous_session = session_name
    file_path = os.path.join(mock_llm_history_dir, f"{session_name}.json")
    mock_isfile.return_value = True
    mock_data = {"messages": [{"role": "user", "content": "Hello"}]}
    mock_read_file.return_value = json.dumps(mock_data)

    result = history_module.read_chat_conversation(mock_shared_context)

    mock_isfile.assert_called_once_with(file_path)
    mock_read_file.assert_called_once_with(file_path)
    assert result == mock_data


@mock.patch("zrb.builtin.llm.history.os.path.isfile", return_value=False)
def test_read_chat_previous_session_not_found(
    mock_isfile, mock_shared_context, mock_llm_history_dir
):
    """Test reading history when previous_session file doesn't exist."""
    session_name = "nonexistent_session"
    mock_shared_context.input.previous_session = session_name
    file_path = os.path.join(mock_llm_history_dir, f"{session_name}.json")

    result = history_module.read_chat_conversation(mock_shared_context)

    mock_isfile.assert_called_once_with(file_path)
    mock_shared_context.log_warning.assert_called_once()
    assert result is None


@mock.patch("zrb.builtin.llm.history.os.path.isfile", return_value=True)
@mock.patch("zrb.builtin.llm.history.read_file", return_value="")
def test_read_chat_previous_session_empty_file(
    mock_read_file, mock_isfile, mock_shared_context, mock_llm_history_dir
):
    """Test reading history when previous_session file is empty."""
    session_name = "empty_session"
    mock_shared_context.input.previous_session = session_name
    file_path = os.path.join(mock_llm_history_dir, f"{session_name}.json")

    result = history_module.read_chat_conversation(mock_shared_context)

    mock_isfile.assert_called_once_with(file_path)
    mock_read_file.assert_called_once_with(file_path)
    mock_shared_context.log_warning.assert_called_once()
    assert result is None


@mock.patch("zrb.builtin.llm.history.os.path.isfile", return_value=True)
@mock.patch("zrb.builtin.llm.history.read_file", return_value="invalid json")
def test_read_chat_previous_session_invalid_json(
    mock_read_file, mock_isfile, mock_shared_context, mock_llm_history_dir
):
    """Test reading history when previous_session file has invalid JSON."""
    session_name = "invalid_json_session"
    mock_shared_context.input.previous_session = session_name
    file_path = os.path.join(mock_llm_history_dir, f"{session_name}.json")

    result = history_module.read_chat_conversation(mock_shared_context)

    mock_isfile.assert_called_once_with(file_path)
    mock_read_file.assert_called_once_with(file_path)
    mock_shared_context.log_warning.assert_called_once()
    assert result is None


@mock.patch("zrb.builtin.llm.history.os.path.isfile")
@mock.patch("zrb.builtin.llm.history.read_file")
def test_read_chat_last_session_exists(
    mock_read_file, mock_isfile, mock_shared_context, mock_llm_history_dir
):
    """Test reading history using last-session file."""
    last_session_name = "last_good_session"
    last_session_path = os.path.join(mock_llm_history_dir, "last-session")
    session_file_path = os.path.join(mock_llm_history_dir, f"{last_session_name}.json")

    # Mock isfile to return True for both last-session and the session file it points to
    def isfile_side_effect(path):
        if path == last_session_path:
            return True
        if path == session_file_path:
            return True
        return False

    mock_isfile.side_effect = isfile_side_effect

    # Mock read_file to return the session name and then the session data
    mock_data = {"messages": [{"role": "user", "content": "From last session"}]}

    def read_file_side_effect(path):
        if path == last_session_path:
            return last_session_name
        if path == session_file_path:
            return json.dumps(mock_data)
        return ""

    mock_read_file.side_effect = read_file_side_effect

    result = history_module.read_chat_conversation(mock_shared_context)

    assert mock_isfile.call_count == 2
    assert mock_read_file.call_count == 2
    assert result == mock_data


@mock.patch("zrb.builtin.llm.history.os.path.isfile")
@mock.patch("zrb.builtin.llm.history.read_file", return_value="")  # Empty last-session
def test_read_chat_last_session_empty(
    mock_read_file, mock_isfile, mock_shared_context, mock_llm_history_dir
):
    """Test reading history when last-session file is empty."""
    last_session_path = os.path.join(mock_llm_history_dir, "last-session")
    mock_isfile.return_value = True  # last-session exists

    result = history_module.read_chat_conversation(mock_shared_context)

    mock_isfile.assert_called_once_with(last_session_path)
    mock_read_file.assert_called_once_with(last_session_path)
    assert result is None


@mock.patch("zrb.builtin.llm.history.os.path.isfile")
@mock.patch("zrb.builtin.llm.history.read_file")
def test_read_chat_last_session_points_to_nonexistent(
    mock_read_file, mock_isfile, mock_shared_context, mock_llm_history_dir
):
    """Test reading history when last-session points to a non-existent file."""
    last_session_name = "ghost_session"
    last_session_path = os.path.join(mock_llm_history_dir, "last-session")
    session_file_path = os.path.join(mock_llm_history_dir, f"{last_session_name}.json")

    # Mock isfile: last-session exists, session file does not
    def isfile_side_effect(path):
        if path == last_session_path:
            return True
        if path == session_file_path:
            return False
        return False

    mock_isfile.side_effect = isfile_side_effect
    mock_read_file.return_value = last_session_name  # read_file returns the name

    result = history_module.read_chat_conversation(mock_shared_context)

    assert mock_isfile.call_count == 2  # Checks last-session, then session file
    mock_read_file.assert_called_once_with(last_session_path)
    mock_shared_context.log_warning.assert_called_once()  # Warns about missing session file
    assert result is None


@mock.patch(
    "zrb.builtin.llm.history.os.path.isfile", return_value=False
)  # No files exist
def test_read_chat_no_previous_no_last(
    mock_isfile, mock_shared_context, mock_llm_history_dir
):
    """Test reading history when no previous_session and no last-session file."""
    last_session_path = os.path.join(mock_llm_history_dir, "last-session")

    result = history_module.read_chat_conversation(mock_shared_context)

    mock_isfile.assert_called_once_with(last_session_path)
    assert result is None


@mock.patch("zrb.builtin.llm.history.os.path.isfile", return_value=True)
@mock.patch("zrb.builtin.llm.history.read_file", side_effect=OSError("Read error"))
def test_read_chat_other_read_error(
    mock_read_file, mock_isfile, mock_shared_context, mock_llm_history_dir
):
    """Test reading history handles generic read errors."""
    session_name = "error_session"
    mock_shared_context.input.previous_session = session_name
    file_path = os.path.join(mock_llm_history_dir, f"{session_name}.json")

    result = history_module.read_chat_conversation(mock_shared_context)

    mock_isfile.assert_called_once_with(file_path)
    mock_read_file.assert_called_once_with(file_path)
    mock_shared_context.log_warning.assert_called_once()
    assert result is None


# --- Tests for write_chat_conversation ---


@mock.patch("zrb.builtin.llm.history.os.makedirs")
@mock.patch("zrb.builtin.llm.history.write_file")
def test_write_chat_success(
    mock_write_file, mock_makedirs, mock_shared_context, mock_llm_history_dir
):
    """Test write_chat_conversation successfully writes history and last-session."""
    session_name = "test_session"
    mock_shared_context.session.name = session_name
    # Use a dictionary for the message
    history_data = ConversationHistoryData(
        messages=[{"role": "user", "content": "Test message"}]
    )
    expected_json = history_data.model_dump_json(indent=2)
    session_file_path = os.path.join(mock_llm_history_dir, f"{session_name}.json")
    last_session_file_path = os.path.join(mock_llm_history_dir, "last-session")

    history_module.write_chat_conversation(mock_shared_context, history_data)

    mock_makedirs.assert_called_once_with(mock_llm_history_dir, exist_ok=True)
    assert mock_write_file.call_count == 2
    mock_write_file.assert_any_call(session_file_path, expected_json)
    mock_write_file.assert_any_call(last_session_file_path, session_name)


def test_write_chat_empty_session_name(mock_shared_context):
    """Test write_chat_conversation logs warning if session name is empty."""
    mock_shared_context.session.name = ""
    history_data = ConversationHistoryData(messages=[])

    history_module.write_chat_conversation(mock_shared_context, history_data)

    mock_shared_context.log_warning.assert_called_once_with(
        "Cannot write history: Session name is empty."
    )


@mock.patch("zrb.builtin.llm.history.os.makedirs")
@mock.patch("zrb.builtin.llm.history.write_file", side_effect=OSError("Write error"))
def test_write_chat_write_error(
    mock_write_file, mock_makedirs, mock_shared_context, mock_llm_history_dir
):
    """Test write_chat_conversation logs error if write_file fails."""
    session_name = "error_session"
    mock_shared_context.session.name = session_name
    history_data = ConversationHistoryData(messages=[])
    session_file_path = os.path.join(mock_llm_history_dir, f"{session_name}.json")

    history_module.write_chat_conversation(mock_shared_context, history_data)

    mock_makedirs.assert_called_once_with(mock_llm_history_dir, exist_ok=True)
    mock_write_file.assert_called_once()  # Only tries to write the session file
    mock_shared_context.log_error.assert_called_once()
    # Check that the error message contains the file path
    assert session_file_path in mock_shared_context.log_error.call_args[0][0]
