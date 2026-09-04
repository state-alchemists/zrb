import json
import os

import pytest

from zrb.llm.history_manager.file_history_manager import FileHistoryManager


@pytest.fixture
def temp_history_dir(tmp_path):
    d = tmp_path / "history"
    d.mkdir()
    return str(d)


def _sample_messages():
    from pydantic_ai.messages import (
        ModelRequest,
        ModelResponse,
        TextPart,
        UserPromptPart,
    )

    return [
        ModelRequest(parts=[UserPromptPart(content="hello")]),
        ModelResponse(parts=[TextPart(content="hi")]),
    ]


def test_filter_part_with_empty_content_skipped(temp_history_dir):
    """Line 126: part with empty string content is skipped in filter."""
    manager = FileHistoryManager(temp_history_dir)
    file_path = os.path.join(temp_history_dir, "empty_content.json")
    data = [
        {
            "kind": "response",
            "parts": [
                {
                    "part_kind": "text",
                    "content": "",  # Empty string → filtered out
                },
                {
                    "part_kind": "text",
                    "content": "valid text",
                },
            ],
            "timestamp": "2026-01-01T00:00:00Z",
            "model_name": "test-model",
        }
    ]
    with open(file_path, "w") as f:
        json.dump(data, f)
    result = manager.load("empty_content")
    # Only the valid text part should remain
    assert len(result) == 1
    assert len(result[0].parts) == 1
    assert result[0].parts[0].content == "valid text"


def test_filter_part_with_none_content_skipped(temp_history_dir):
    """Line 131: part with None content is skipped in filter."""
    manager = FileHistoryManager(temp_history_dir)
    file_path = os.path.join(temp_history_dir, "none_content.json")
    data = [
        {
            "kind": "response",
            "parts": [
                {
                    "part_kind": "text",
                    "content": None,  # None content → filtered out
                },
                {
                    "part_kind": "text",
                    "content": "valid",
                },
            ],
            "timestamp": "2026-01-01T00:00:00Z",
            "model_name": "test-model",
        }
    ]
    with open(file_path, "w") as f:
        json.dump(data, f)
    result = manager.load("none_content")
    assert len(result) == 1
    assert len(result[0].parts) == 1


def test_filter_part_is_none_skipped(temp_history_dir):
    """Lines 135-136: None part in parts list is skipped."""
    manager = FileHistoryManager(temp_history_dir)
    file_path = os.path.join(temp_history_dir, "none_part.json")
    data = [
        {
            "kind": "request",
            "parts": [
                {
                    "part_kind": "user-prompt",
                    "content": "hello",
                    "timestamp": "2026-01-01T00:00:00Z",
                },
                None,  # None part → filtered out
            ],
            "timestamp": None,
            "instructions": None,
        }
    ]
    with open(file_path, "w") as f:
        json.dump(data, f)
    result = manager.load("none_part")
    assert len(result) == 1
    assert len(result[0].parts) == 1


def test_delegated_history_saved_under_subagent_subdirectory(temp_history_dir):
    """A delegated conversation saves to LLM_HISTORY_DIR/subagent/<agent-type>/
    — never flat in the history root next to ordinary sessions."""
    from zrb.llm.util.subagent_session_naming import format_delegated_session_name

    name = format_delegated_session_name("sess1", "researcher", "a1b2c3d4")
    manager = FileHistoryManager(temp_history_dir)
    manager.update(name, _sample_messages())
    manager.save(name, write_backup=False)

    expected = os.path.join(temp_history_dir, "subagent", "researcher", f"{name}.json")
    assert os.path.exists(expected)
    assert not os.path.exists(os.path.join(temp_history_dir, f"{name}.json"))

    loaded = FileHistoryManager(temp_history_dir).load(name)
    assert len(loaded) == 2
    assert loaded[0].parts[0].content == "hello"


def test_ordinary_session_stays_flat_in_history_root(temp_history_dir):
    """The subagent/<agent-type>/ layout must not disturb ordinary sessions."""
    manager = FileHistoryManager(temp_history_dir)
    manager.update("my-session", _sample_messages())
    manager.save("my-session", write_backup=False)

    assert os.path.exists(os.path.join(temp_history_dir, "my-session.json"))
    assert not os.path.exists(os.path.join(temp_history_dir, "subagent"))


def test_delegated_history_backup_lands_next_to_main_file(temp_history_dir):
    """A delegated conversation's timestamped backup goes into the same
    subagent/<agent-type>/ directory as its main file, not the history root."""
    from zrb.llm.util.subagent_session_naming import format_delegated_session_name

    name = format_delegated_session_name("sess1", "code-reviewer", "e5f6a7b8")
    manager = FileHistoryManager(temp_history_dir)
    manager.update(name, _sample_messages())
    manager.save(name)

    subdir = os.path.join(temp_history_dir, "subagent", "code-reviewer")
    files = os.listdir(subdir)
    assert f"{name}.json" in files
    assert len(files) == 2  # main + one backup
    # The backup is timestamped (not a second copy of the main name).
    assert any(f != f"{name}.json" for f in files)
    assert os.listdir(temp_history_dir) == ["subagent"]


def test_delegated_history_rotation_scoped_to_subdirectory(
    temp_history_dir, monkeypatch
):
    """Backup rotation for a delegated conversation only ever touches files
    inside its own subagent/<agent-type>/ directory."""
    from zrb.llm.util.subagent_session_naming import format_delegated_session_name

    monkeypatch.setenv("ZRB_LLM_HISTORY_BACKUP_RETAIN", "2")
    name = format_delegated_session_name("sess1", "researcher", "a1b2c3d4")
    manager = FileHistoryManager(temp_history_dir)

    for i in range(5):
        manager.update(name, _sample_messages())
        manager.save(name)

    subdir = os.path.join(temp_history_dir, "subagent", "researcher")
    files = os.listdir(subdir)
    assert f"{name}.json" in files  # main survives rotation
    assert len(files) == 3  # main + the 2 most recent backups
    assert os.listdir(temp_history_dir) == ["subagent"]


def test_delegated_history_legacy_flat_file_still_loads(temp_history_dir):
    """Transcripts written before the subagent/<agent-type>/ layout (flat in
    the history root) must keep loading via fallback — no auto-migration."""
    from zrb.llm.util.subagent_session_naming import format_delegated_session_name

    name = format_delegated_session_name("sess1", "researcher", "a1b2c3d4")
    manager = FileHistoryManager(temp_history_dir)
    manager.update(name, _sample_messages())
    manager.save(name, write_backup=False)
    legacy_path = os.path.join(temp_history_dir, f"{name}.json")
    os.replace(
        os.path.join(temp_history_dir, "subagent", "researcher", f"{name}.json"),
        legacy_path,
    )

    loaded = FileHistoryManager(temp_history_dir).load(name)
    assert len(loaded) == 2  # read from the legacy flat location

    # A subsequent save writes to the new layout; both remain readable.
    manager2 = FileHistoryManager(temp_history_dir)
    manager2.update(name, _sample_messages())
    manager2.save(name, write_backup=False)
    assert os.path.exists(
        os.path.join(temp_history_dir, "subagent", "researcher", f"{name}.json")
    )
    assert len(FileHistoryManager(temp_history_dir).load(name)) == 2


def test_delegated_history_search_scans_subagent_subdirectories(temp_history_dir):
    """search() finds delegated transcripts that live under subagent/<agent>/,
    alongside ordinary flat sessions."""
    from zrb.llm.util.subagent_session_naming import format_delegated_session_name

    researcher = format_delegated_session_name("sess1", "researcher", "a1b2c3d4")
    reviewer = format_delegated_session_name("sess1", "code-reviewer", "e5f6a7b8")
    manager = FileHistoryManager(temp_history_dir)
    manager.update(researcher, _sample_messages())
    manager.update(reviewer, _sample_messages())
    manager.save(researcher, write_backup=False)
    manager.save(reviewer, write_backup=False)
    (open(os.path.join(temp_history_dir, "apple.json"), "w")).close()

    results = manager.search("")
    assert researcher in results
    assert reviewer in results
    assert "apple" in results
    assert manager.search("researcher") == [researcher]
