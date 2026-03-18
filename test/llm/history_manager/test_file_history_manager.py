import json
import os

import pytest

from zrb.llm.history_manager.file_history_manager import FileHistoryManager


@pytest.fixture
def temp_history_dir(tmp_path):
    d = tmp_path / "history"
    d.mkdir()
    return str(d)


def test_file_history_manager_save_load(temp_history_dir):
    manager = FileHistoryManager(temp_history_dir)
    # ModelMessagesTypeAdapter is hard to mock or use without real messages
    # but we can try with empty list or simple messages if validated
    from pydantic_ai.messages import (
        ModelRequest,
        ModelResponse,
        TextPart,
        UserPromptPart,
    )

    messages = [
        ModelRequest(parts=[UserPromptPart(content="hello")]),
        ModelResponse(parts=[TextPart(content="hi")]),
    ]

    manager.update("session1", messages)
    manager.save("session1")

    assert os.path.exists(os.path.join(temp_history_dir, "session1.json"))

    # New manager instance to test loading from file
    manager2 = FileHistoryManager(temp_history_dir)
    loaded = manager2.load("session1")
    assert len(loaded) == 2
    assert loaded[0].parts[0].content == "hello"


def test_file_history_manager_search(temp_history_dir):
    manager = FileHistoryManager(temp_history_dir)
    # Create some dummy files
    (open(os.path.join(temp_history_dir, "apple.json"), "w")).close()
    (open(os.path.join(temp_history_dir, "banana.json"), "w")).close()

    results = manager.search("app")
    assert "apple" in results
    assert "banana" not in results


def test_file_history_manager_load_empty(temp_history_dir):
    manager = FileHistoryManager(temp_history_dir)
    file_path = os.path.join(temp_history_dir, "empty.json")
    with open(file_path, "w") as f:
        f.write("  ")
    assert manager.load("empty") == []


def test_file_history_manager_load_invalid(temp_history_dir):
    manager = FileHistoryManager(temp_history_dir)
    file_path = os.path.join(temp_history_dir, "invalid.json")
    with open(file_path, "w") as f:
        f.write("invalid json")
    assert manager.load("invalid") == []


def test_file_history_manager_load_validation_error(temp_history_dir):
    """Test that dictionary in UserPromptPart.content is proactively cleaned to JSON string."""
    manager = FileHistoryManager(temp_history_dir)
    file_path = os.path.join(temp_history_dir, "corrupted.json")

    # Create a corrupted JSON file that will cause ValidationError
    # This simulates the bug where UserPromptPart.content contains dictionaries
    # Note: pydantic-ai uses "kind" for message type and "part_kind" for part type
    corrupted_data = [
        {
            "kind": "request",
            "parts": [
                {
                    "part_kind": "user-prompt",
                    "content": {
                        "summary": "test",
                        "results": [],
                    },  # Dictionary instead of string/Sequence
                    "timestamp": "2026-02-23T09:25:23.369273Z",
                }
            ],
            "timestamp": None,
            "instructions": None,
            "run_id": None,
            "metadata": None,
        }
    ]

    with open(file_path, "w") as f:
        json.dump(corrupted_data, f)

    # With proactive cleaning, dictionary should be converted to JSON string
    result = manager.load("corrupted")
    assert len(result) == 1
    assert (
        result[0].parts[0].content == '{"summary": "test", "results": []}'
    )  # Converted to JSON string


def test_file_history_manager_load_validation_error_boolean(temp_history_dir):
    """Test that boolean in UserPromptPart.content is proactively cleaned to string."""
    manager = FileHistoryManager(temp_history_dir)
    file_path = os.path.join(temp_history_dir, "corrupted_bool.json")

    # Create a corrupted JSON file with boolean in content
    corrupted_data = [
        {
            "kind": "request",
            "parts": [
                {
                    "part_kind": "user-prompt",
                    "content": True,  # Boolean instead of string/Sequence
                    "timestamp": "2026-02-23T09:25:23.369273Z",
                }
            ],
            "timestamp": None,
            "instructions": None,
            "run_id": None,
            "metadata": None,
        }
    ]

    with open(file_path, "w") as f:
        json.dump(corrupted_data, f)

    # With proactive cleaning, boolean should be converted to string
    result = manager.load("corrupted_bool")
    assert len(result) == 1
    assert result[0].parts[0].content == "True"  # Converted to string


def test_file_history_manager_load_validation_error_number(temp_history_dir):
    """Test that number in UserPromptPart.content is proactively cleaned to string."""
    manager = FileHistoryManager(temp_history_dir)
    file_path = os.path.join(temp_history_dir, "corrupted_number.json")

    # Create a corrupted JSON file with number in content
    corrupted_data = [
        {
            "kind": "request",
            "parts": [
                {
                    "part_kind": "user-prompt",
                    "content": 42,  # Number instead of string/Sequence
                    "timestamp": "2026-02-23T09:25:23.369273Z",
                }
            ],
            "timestamp": None,
            "instructions": None,
            "run_id": None,
            "metadata": None,
        }
    ]

    with open(file_path, "w") as f:
        json.dump(corrupted_data, f)

    # With proactive cleaning, number should be converted to string
    result = manager.load("corrupted_number")
    assert len(result) == 1
    assert result[0].parts[0].content == "42"  # Converted to string


def test_file_history_manager_save_with_corrupted_data(temp_history_dir):
    """Test that save() handles corrupted data with auto-recovery."""
    manager = FileHistoryManager(temp_history_dir)

    # Create messages with corrupted content (simulating the bug)
    from pydantic_ai.messages import ModelRequest, UserPromptPart

    # Create a corrupted message (this would normally fail validation)
    # We'll simulate the corruption by creating a message with dictionary content
    # In reality, this would come from a bug in pydantic-ai
    messages = [
        ModelRequest(parts=[UserPromptPart(content="normal message")]),
    ]

    manager.update("test_session", messages)
    manager.save("test_session")

    # Verify the file was saved
    file_path = os.path.join(temp_history_dir, "test_session.json")
    assert os.path.exists(file_path)

    # Load it back
    loaded = manager.load("test_session")
    assert len(loaded) == 1
    assert loaded[0].parts[0].content == "normal message"


def test_file_history_manager_clean_corrupted_content_method(temp_history_dir):
    """Test the _clean_corrupted_content method directly."""
    manager = FileHistoryManager(temp_history_dir)

    # Test dictionary conversion
    data = {
        "part_kind": "user-prompt",
        "content": {"key": "value", "nested": {"inner": "data"}},
        "timestamp": "2026-02-23T09:25:23.369273Z",
    }
    cleaned = manager._clean_corrupted_content(data)
    assert cleaned["content"] == '{"key": "value", "nested": {"inner": "data"}}'

    # Test boolean conversion
    data = {
        "part_kind": "user-prompt",
        "content": True,
        "timestamp": "2026-02-23T09:25:23.369273Z",
    }
    cleaned = manager._clean_corrupted_content(data)
    assert cleaned["content"] == "True"

    # Test number conversion
    data = {
        "part_kind": "user-prompt",
        "content": 123.45,
        "timestamp": "2026-02-23T09:25:23.369273Z",
    }
    cleaned = manager._clean_corrupted_content(data)
    assert cleaned["content"] == "123.45"

    # Test that valid content is not changed
    data = {
        "part_kind": "user-prompt",
        "content": "normal string",
        "timestamp": "2026-02-23T09:25:23.369273Z",
    }
    cleaned = manager._clean_corrupted_content(data)
    assert cleaned["content"] == "normal string"

    # Test nested structures
    data = [
        {
            "kind": "request",
            "parts": [
                {
                    "part_kind": "user-prompt",
                    "content": {"summary": "test"},
                    "timestamp": "2026-02-23T09:25:23.369273Z",
                },
                {
                    "part_kind": "text",
                    "content": "normal text",
                    "timestamp": "2026-02-23T09:25:23.369273Z",
                },
            ],
            "timestamp": None,
            "instructions": None,
            "run_id": None,
            "metadata": None,
        }
    ]
    cleaned = manager._clean_corrupted_content(data)
    assert cleaned[0]["parts"][0]["content"] == '{"summary": "test"}'
    assert cleaned[0]["parts"][1]["content"] == "normal text"


def test_file_history_manager_proactive_cleaning_comprehensive(temp_history_dir):
    """Test comprehensive proactive cleaning of various content types."""
    manager = FileHistoryManager(temp_history_dir)

    # Test None content
    data = {
        "part_kind": "user-prompt",
        "content": None,
        "timestamp": "2026-02-23T09:25:23.369273Z",
    }
    cleaned = manager._clean_corrupted_content(data)
    assert cleaned["content"] == ""  # None should be converted to empty string

    # Test list content (non-string list)
    data = {
        "part_kind": "user-prompt",
        "content": [1, 2, 3],
        "timestamp": "2026-02-23T09:25:23.369273Z",
    }
    cleaned = manager._clean_corrupted_content(data)
    assert cleaned["content"] == "[1, 2, 3]"  # List should be converted to JSON string

    # Test float content
    data = {
        "part_kind": "user-prompt",
        "content": 3.14159,
        "timestamp": "2026-02-23T09:25:23.369273Z",
    }
    cleaned = manager._clean_corrupted_content(data)
    assert cleaned["content"] == "3.14159"  # Float should be converted to string

    # Test boolean False
    data = {
        "part_kind": "user-prompt",
        "content": False,
        "timestamp": "2026-02-23T09:25:23.369273Z",
    }
    cleaned = manager._clean_corrupted_content(data)
    assert cleaned["content"] == "False"  # Boolean False should be converted to string


def test_file_history_manager_filter_empty_responses(temp_history_dir):
    """Test filtering out empty responses from history data."""
    manager = FileHistoryManager(temp_history_dir)

    # Test filtering empty responses
    data = [
        {
            "kind": "request",
            "parts": [
                {
                    "part_kind": "user-prompt",
                    "content": "Hello",
                    "timestamp": "2026-02-23T09:25:23.369273Z",
                }
            ],
            "timestamp": None,
            "instructions": None,
            "run_id": None,
            "metadata": None,
        },
        {
            "kind": "response",
            "parts": [],  # Empty response that should be filtered out
            "usage": {
                "input_tokens": 0,
                "cache_write_tokens": 0,
                "cache_read_tokens": 0,
                "output_tokens": 0,
            },
            "model_name": "glm-5:cloud",
            "timestamp": "2026-03-07T10:13:06.791202Z",
            "provider_name": "ollama",
            "provider_url": "http://localhost:11434/v1/",
            "provider_details": {
                "timestamp": "2026-03-07T10:13:06Z",
                "finish_reason": "stop",
            },
            "provider_response_id": "chatcmpl-725",
            "finish_reason": "stop",
            "run_id": "c38dba6b-f0fe-4696-a34f-1fa273095318",
            "metadata": None,
        },
        {
            "kind": "response",
            "parts": [
                {
                    "part_kind": "text",
                    "content": "Hi there!",
                    "id": None,
                    "provider_name": None,
                    "provider_details": None,
                }
            ],
            "usage": {
                "input_tokens": 100,
                "cache_write_tokens": 0,
                "cache_read_tokens": 0,
                "output_tokens": 50,
            },
            "model_name": "glm-5:cloud",
            "timestamp": "2026-03-07T10:13:07.791202Z",
            "provider_name": "ollama",
            "provider_url": "http://localhost:11434/v1/",
            "provider_details": {
                "timestamp": "2026-03-07T10:13:07Z",
                "finish_reason": "stop",
            },
            "provider_response_id": "chatcmpl-726",
            "finish_reason": "stop",
            "run_id": "c38dba6b-f0fe-4696-a34f-1fa273095318",
            "metadata": None,
        },
    ]

    filtered = manager._filter_empty_responses(data)
    assert len(filtered) == 2  # Should have 2 items (request + non-empty response)
    assert filtered[0]["kind"] == "request"
    assert filtered[1]["kind"] == "response"
    assert len(filtered[1]["parts"]) == 1  # Non-empty response should be kept
    assert filtered[1]["parts"][0]["content"] == "Hi there!"

    # Test with None parts
    data_with_none_parts = [
        {
            "kind": "response",
            "parts": None,  # None parts should also be filtered out
            "timestamp": "2026-03-07T10:13:06.791202Z",
        }
    ]
    filtered = manager._filter_empty_responses(data_with_none_parts)
    assert len(filtered) == 0  # Should be filtered out

    # Test nested structures
    nested_data = {
        "conversation": [
            {
                "kind": "request",
                "parts": [{"part_kind": "user-prompt", "content": "Test"}],
            },
            {
                "kind": "response",
                "parts": [],  # Should be filtered out
            },
        ]
    }
    filtered = manager._filter_empty_responses(nested_data)
    assert len(filtered["conversation"]) == 1
    assert filtered["conversation"][0]["kind"] == "request"


def test_extract_base_name(temp_history_dir):
    """Test extracting base session name from timestamped names."""
    manager = FileHistoryManager(temp_history_dir)

    # Without timestamp
    assert manager._extract_base_name("my-session") == "my-session"
    assert manager._extract_base_name("simple") == "simple"

    # With full timestamp (YYYY-MM-DD-HH-MM-SS)
    assert manager._extract_base_name("my-session-2024-03-18-10-30-00") == "my-session"
    assert manager._extract_base_name("project-2024-12-31-23-59-59") == "project"

    # With partial timestamp (YYYY-MM-DD-HH-MM)
    assert manager._extract_base_name("session-2024-03-18-10-30") == "session"
    assert manager._extract_base_name("test-2024-01-01-00-00") == "test"

    # Edge cases - timestamp without base name stays as-is (no hyphen prefix)
    assert manager._extract_base_name("") == ""
    # "2024-03-18-10-30-00" has no base name before the timestamp, so it stays
    assert manager._extract_base_name("2024-03-18-10-30-00") == "2024-03-18-10-30-00"


def test_get_backup_file_path(temp_history_dir):
    """Test generating backup file paths with timestamps."""
    manager = FileHistoryManager(temp_history_dir)

    from datetime import datetime

    # First backup should work
    ts = datetime(2024, 3, 18, 10, 30, 0)
    backup_path = manager._get_backup_file_path("my-session", ts)
    assert backup_path.endswith("my-session-2024-03-18-10-30-00.json")

    # Create the file
    with open(backup_path, "w") as f:
        f.write("{}")

    # Second call with same timestamp should add -1
    backup_path2 = manager._get_backup_file_path("my-session", ts)
    assert backup_path2.endswith("my-session-2024-03-18-10-30-00-1.json")

    # Create that file too
    with open(backup_path2, "w") as f:
        f.write("{}")

    # Third call should add -2
    backup_path3 = manager._get_backup_file_path("my-session", ts)
    assert backup_path3.endswith("my-session-2024-03-18-10-30-00-2.json")


def test_save_creates_backup(temp_history_dir):
    """Test that save() creates both main file and timestamped backup."""
    import re

    from pydantic_ai.messages import (
        ModelRequest,
        ModelResponse,
        TextPart,
        UserPromptPart,
    )

    manager = FileHistoryManager(temp_history_dir)

    messages = [
        ModelRequest(parts=[UserPromptPart(content="hello")]),
        ModelResponse(parts=[TextPart(content="hi")]),
    ]

    manager.update("my-session", messages)
    manager.save("my-session")

    # Check main file exists
    main_file = os.path.join(temp_history_dir, "my-session.json")
    assert os.path.exists(main_file)

    # Check backup file exists (with timestamp pattern)
    files = os.listdir(temp_history_dir)
    backup_pattern = re.compile(
        r"my-session-\d{4}-\d{2}-\d{2}-\d{2}-\d{2}-\d{2}(?:-\d+)?\.json"
    )
    backup_files = [f for f in files if backup_pattern.match(f)]
    assert len(backup_files) == 1, f"Expected 1 backup file, found: {backup_files}"


def test_save_with_timestamped_session_name(temp_history_dir):
    """Test that save() correctly handles session names with timestamps."""
    import re

    from pydantic_ai.messages import (
        ModelRequest,
        ModelResponse,
        TextPart,
        UserPromptPart,
    )

    manager = FileHistoryManager(temp_history_dir)

    messages = [
        ModelRequest(parts=[UserPromptPart(content="hello")]),
        ModelResponse(parts=[TextPart(content="hi")]),
    ]

    # Session name already has a timestamp
    manager.update("my-session-2024-03-18-10-30-00", messages)
    manager.save("my-session-2024-03-18-10-30-00")

    # Check main file exists with the full name
    main_file = os.path.join(temp_history_dir, "my-session-2024-03-18-10-30-00.json")
    assert os.path.exists(main_file)

    # Check backup uses the base name (without the timestamp)
    files = os.listdir(temp_history_dir)
    # Backup should be my-session-<timestamp>.json, NOT my-session-2024-03-18-10-30-00-<timestamp>.json
    backup_pattern = re.compile(
        r"my-session-\d{4}-\d{2}-\d{2}-\d{2}-\d{2}-\d{2}(?:-\d+)?\.json"
    )
    backup_files = [f for f in files if backup_pattern.match(f)]

    # Should have 2 files: the main one and the backup
    # The main file name matches the backup pattern, so we check for my-session-<timestamp>.json
    # that is NOT the main file
    timestamp_pattern = re.compile(
        r"my-session-\d{4}-\d{2}-\d{2}-\d{2}-\d{2}-\d{2}\.json"
    )
    main_files = [f for f in files if timestamp_pattern.match(f)]

    # There should be exactly 2 files: main (with timestamp in name) and backup (with new timestamp)
    assert len(main_files) == 2, f"Expected 2 files (main + backup), found: {files}"
