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
    """Test that ValidationError from pydantic triggers auto-recovery."""
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
                    "content": {"summary": "test", "results": []},  # Dictionary instead of string/Sequence
                    "timestamp": "2026-02-23T09:25:23.369273Z"
                }
            ],
            "timestamp": None,
            "instructions": None,
            "run_id": None,
            "metadata": None
        }
    ]
    
    with open(file_path, "w") as f:
        json.dump(corrupted_data, f)
    
    # With auto-recovery, should recover the corrupted data
    result = manager.load("corrupted")
    assert len(result) == 1
    assert result[0].parts[0].content == '{"summary": "test", "results": []}'  # Converted to JSON string


def test_file_history_manager_load_validation_error_boolean(temp_history_dir):
    """Test ValidationError for boolean in UserPromptPart.content triggers auto-recovery."""
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
                    "timestamp": "2026-02-23T09:25:23.369273Z"
                }
            ],
            "timestamp": None,
            "instructions": None,
            "run_id": None,
            "metadata": None
        }
    ]
    
    with open(file_path, "w") as f:
        json.dump(corrupted_data, f)
    
    # With auto-recovery, should recover the corrupted data
    result = manager.load("corrupted_bool")
    assert len(result) == 1
    assert result[0].parts[0].content == "True"  # Converted to string


def test_file_history_manager_load_validation_error_number(temp_history_dir):
    """Test ValidationError for number in UserPromptPart.content triggers auto-recovery."""
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
                    "timestamp": "2026-02-23T09:25:23.369273Z"
                }
            ],
            "timestamp": None,
            "instructions": None,
            "run_id": None,
            "metadata": None
        }
    ]
    
    with open(file_path, "w") as f:
        json.dump(corrupted_data, f)
    
    # With auto-recovery, should recover the corrupted data
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
        "timestamp": "2026-02-23T09:25:23.369273Z"
    }
    cleaned = manager._clean_corrupted_content(data)
    assert cleaned["content"] == '{"key": "value", "nested": {"inner": "data"}}'
    
    # Test boolean conversion
    data = {
        "part_kind": "user-prompt",
        "content": True,
        "timestamp": "2026-02-23T09:25:23.369273Z"
    }
    cleaned = manager._clean_corrupted_content(data)
    assert cleaned["content"] == "True"
    
    # Test number conversion
    data = {
        "part_kind": "user-prompt",
        "content": 123.45,
        "timestamp": "2026-02-23T09:25:23.369273Z"
    }
    cleaned = manager._clean_corrupted_content(data)
    assert cleaned["content"] == "123.45"
    
    # Test that valid content is not changed
    data = {
        "part_kind": "user-prompt",
        "content": "normal string",
        "timestamp": "2026-02-23T09:25:23.369273Z"
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
                    "timestamp": "2026-02-23T09:25:23.369273Z"
                },
                {
                    "part_kind": "text",
                    "content": "normal text",
                    "timestamp": "2026-02-23T09:25:23.369273Z"
                }
            ],
            "timestamp": None,
            "instructions": None,
            "run_id": None,
            "metadata": None
        }
    ]
    cleaned = manager._clean_corrupted_content(data)
    assert cleaned[0]["parts"][0]["content"] == '{"summary": "test"}'
    assert cleaned[0]["parts"][1]["content"] == "normal text"
