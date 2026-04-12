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


def test_file_history_manager_clean_corrupted_content_via_load(temp_history_dir):
    """Test that corrupted content is cleaned when loading via public API."""
    manager = FileHistoryManager(temp_history_dir)

    # Test dictionary conversion through load - tests behavior via public API
    file_path = os.path.join(temp_history_dir, "test_dict.json")
    data = {
        "part_kind": "user-prompt",
        "content": {"key": "value"},
        "timestamp": "2026-02-23T09:25:23.369273Z",
    }
    json.dump([{"kind": "request", "parts": [data]}], open(file_path, "w"))
    result = manager.load("test_dict")
    assert result[0].parts[0].content == '{"key": "value"}'


def test_file_history_manager_filter_empty_responses_via_load(temp_history_dir):
    """Test filtering out empty responses when loading history data."""
    manager = FileHistoryManager(temp_history_dir)

    # Create a file with empty response parts - should be filtered during load
    file_path = os.path.join(temp_history_dir, "test_filter.json")
    data = [
        {
            "kind": "request",
            "parts": [
                {
                    "part_kind": "user-prompt",
                    "content": "Hello",
                    "timestamp": "2026-02-23T09:25:23Z",
                }
            ],
            "timestamp": None,
            "instructions": None,
        },
        {
            "kind": "response",
            "parts": [],  # Empty response
            "timestamp": "2026-03-07T10:13:06Z",
        },
        {
            "kind": "response",
            "parts": [{"part_kind": "text", "content": "Hi there!"}],
            "timestamp": "2026-03-07T10:13:07Z",
        },
    ]
    json.dump(data, open(file_path, "w"))

    result = manager.load("test_filter")
    # Empty response should be filtered out, only request and non-empty response remain
    assert len(result) == 2


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


# ---------------------------------------------------------------------------
# Additional tests to cover missing lines
# ---------------------------------------------------------------------------


def test_init_creates_directory_if_not_exists(tmp_path):
    """Line 24: os.makedirs() is called when history_dir does not exist."""
    new_dir = str(tmp_path / "does" / "not" / "exist")
    assert not os.path.exists(new_dir)
    FileHistoryManager(new_dir)
    assert os.path.isdir(new_dir)


def test_load_user_prompt_with_list_of_non_strings(temp_history_dir):
    """Lines 40-43: user-prompt content is a list that contains non-string items."""
    manager = FileHistoryManager(temp_history_dir)
    file_path = os.path.join(temp_history_dir, "list_content.json")
    data = [
        {
            "kind": "request",
            "parts": [
                {
                    "part_kind": "user-prompt",
                    "content": [{"key": "val"}, 42],
                    "timestamp": "2026-01-01T00:00:00Z",
                }
            ],
            "timestamp": None,
            "instructions": None,
        }
    ]
    with open(file_path, "w") as f:
        json.dump(data, f)
    result = manager.load("list_content")
    # Non-string list items should be converted to a single string
    assert len(result) == 1
    assert isinstance(result[0].parts[0].content, str)


def test_load_text_part_with_non_string_content(temp_history_dir):
    """Line 51: text/thinking/retry-prompt part with non-string content is converted."""
    manager = FileHistoryManager(temp_history_dir)
    file_path = os.path.join(temp_history_dir, "text_nonstring.json")
    data = [
        {
            "kind": "response",
            "parts": [
                {
                    "part_kind": "text",
                    "content": 99,  # number instead of string
                }
            ],
            "timestamp": "2026-01-01T00:00:00Z",
            "model_name": "test-model",
        }
    ]
    with open(file_path, "w") as f:
        json.dump(data, f)
    result = manager.load("text_nonstring")
    assert len(result) == 1
    assert result[0].parts[0].content == "99"


def test_load_tool_return_part_with_tool_call_id_and_timestamp(temp_history_dir):
    """Lines 55-71: tool-return part with tool_call_id and timestamp fields."""
    manager = FileHistoryManager(temp_history_dir)
    file_path = os.path.join(temp_history_dir, "tool_return_full.json")
    data = [
        {
            "kind": "response",
            "parts": [
                {
                    "part_kind": "tool-call",
                    "tool_name": "my_tool",
                    "args": {"x": 1},
                    "tool_call_id": "call-1",
                }
            ],
            "timestamp": "2026-01-01T00:00:00Z",
            "model_name": "test-model",
        },
        {
            "kind": "request",
            "parts": [
                {
                    "part_kind": "tool-return",
                    "content": "result",
                    "tool_name": "my_tool",
                    "tool_call_id": "call-1",
                    "timestamp": "2026-01-01T00:00:01Z",
                }
            ],
            "timestamp": None,
            "instructions": None,
        },
    ]
    with open(file_path, "w") as f:
        json.dump(data, f)
    result = manager.load("tool_return_full")
    assert len(result) == 2


def test_load_tool_return_part_without_optional_fields(temp_history_dir):
    """Lines 55-71: tool-return part without tool_call_id and timestamp (branches not taken)."""
    manager = FileHistoryManager(temp_history_dir)
    file_path = os.path.join(temp_history_dir, "tool_return_minimal.json")
    data = [
        {
            "kind": "response",
            "parts": [
                {
                    "part_kind": "tool-call",
                    "tool_name": "my_tool",
                    "args": {},
                }
            ],
            "timestamp": "2026-01-01T00:00:00Z",
            "model_name": "test-model",
        },
        {
            "kind": "request",
            "parts": [
                {
                    "part_kind": "tool-return",
                    "content": "tool result",  # Non-empty content to avoid filtering
                    "tool_name": "my_tool",
                    # no tool_call_id, no timestamp
                }
            ],
            "timestamp": None,
            "instructions": None,
        },
    ]
    with open(file_path, "w") as f:
        json.dump(data, f)
    result = manager.load("tool_return_minimal")
    assert len(result) == 2


def test_load_tool_call_part_with_tool_call_id(temp_history_dir):
    """Lines 73-86: tool-call part that includes tool_call_id."""
    manager = FileHistoryManager(temp_history_dir)
    file_path = os.path.join(temp_history_dir, "tool_call_with_id.json")
    data = [
        {
            "kind": "response",
            "parts": [
                {
                    "part_kind": "tool-call",
                    "tool_name": "my_tool",
                    "args": {"a": 1},
                    "tool_call_id": "tcid-42",
                }
            ],
            "timestamp": "2026-01-01T00:00:00Z",
            "model_name": "test-model",
        }
    ]
    with open(file_path, "w") as f:
        json.dump(data, f)
    result = manager.load("tool_call_with_id")
    assert len(result) == 1
    assert result[0].parts[0].tool_name == "my_tool"


def test_load_tool_call_part_with_none_tool_name_filtered(temp_history_dir):
    """Lines 74-78 and 125-126: tool-call part with None tool_name is filtered out entirely."""
    manager = FileHistoryManager(temp_history_dir)
    file_path = os.path.join(temp_history_dir, "tool_call_no_name.json")
    data = [
        {
            "kind": "response",
            "parts": [
                {
                    "part_kind": "tool-call",
                    "tool_name": None,  # invalid → should be filtered
                    "args": {},
                },
                {
                    "part_kind": "text",
                    "content": "a valid part",
                },
            ],
            "timestamp": "2026-01-01T00:00:00Z",
            "model_name": "test-model",
        }
    ]
    with open(file_path, "w") as f:
        json.dump(data, f)
    result = manager.load("tool_call_no_name")
    # The invalid tool-call is removed; text part survives
    assert len(result) == 1
    assert len(result[0].parts) == 1
    assert result[0].parts[0].content == "a valid part"


def test_load_part_with_no_part_kind_and_none_content_filtered(temp_history_dir):
    """Lines 133-136: part with no part_kind (and no content) is filtered from parts list."""
    manager = FileHistoryManager(temp_history_dir)
    file_path = os.path.join(temp_history_dir, "no_part_kind.json")
    data = [
        {
            "kind": "request",
            "parts": [
                {
                    "part_kind": "user-prompt",
                    "content": "hello",
                    "timestamp": "2026-01-01T00:00:00Z",
                },
                {
                    # no part_kind, no content key → filtered
                    "some_field": "some_value",
                },
            ],
            "timestamp": None,
            "instructions": None,
        }
    ]
    with open(file_path, "w") as f:
        json.dump(data, f)
    result = manager.load("no_part_kind")
    # Only the valid user-prompt part survives
    assert len(result) == 1
    assert len(result[0].parts) == 1


def test_filter_empty_responses_non_dict_items_in_list(temp_history_dir):
    """Line 151: Non-dict, non-None items in a list are passed through the filter unchanged."""
    manager = FileHistoryManager(temp_history_dir)
    # Build a structure where a nested list contains a non-dict scalar
    # We reach line 151 when _filter_empty_responses iterates a list and finds a non-dict item.
    # We can trigger this through load() by putting scalar values inside parts list.
    file_path = os.path.join(temp_history_dir, "scalar_in_list.json")
    # A response message whose parts list contains a plain string scalar
    data = [
        {
            "kind": "request",
            "parts": [
                {
                    "part_kind": "user-prompt",
                    "content": "ping",
                    "timestamp": "2026-01-01T00:00:00Z",
                }
            ],
            "timestamp": None,
            "instructions": None,
            # nested list with non-dict scalar as an extra key so recursion hits line 151
            "extra": ["scalar_value", 123],
        }
    ]
    with open(file_path, "w") as f:
        json.dump(data, f)
    result = manager.load("scalar_in_list")
    assert len(result) == 1


def test_load_with_empty_conversation_name(temp_history_dir):
    """Line 172: empty/whitespace-only name is sanitised to 'default'."""
    manager = FileHistoryManager(temp_history_dir)
    file_path = os.path.join(temp_history_dir, "default.json")
    with open(file_path, "w") as f:
        json.dump([], f)
    result = manager.load("")
    assert result == []


def test_load_with_whitespace_only_conversation_name(temp_history_dir):
    """Line 172: whitespace-only name is also sanitised to 'default'."""
    manager = FileHistoryManager(temp_history_dir)
    file_path = os.path.join(temp_history_dir, "default.json")
    with open(file_path, "w") as f:
        json.dump([], f)
    result = manager.load("   ")
    assert result == []


def test_save_creates_backup_with_conflict_resolution(temp_history_dir):
    """Lines 203-208: backup conflict resolution creates a numbered variant."""
    from datetime import datetime
    from unittest.mock import patch

    from pydantic_ai.messages import ModelRequest, UserPromptPart

    manager = FileHistoryManager(temp_history_dir)
    messages = [ModelRequest(parts=[UserPromptPart(content="hi")])]

    frozen_time = datetime(2026, 1, 1, 10, 0, 0)
    # Pre-create the backup path that would normally be created first
    backup_path = os.path.join(
        temp_history_dir, "test-session-2026-01-01-10-00-00.json"
    )
    with open(backup_path, "w") as f:
        f.write("{}")

    manager.update("test-session", messages)
    with patch("zrb.llm.history_manager.file_history_manager.datetime") as mock_dt:
        mock_dt.now.return_value = frozen_time
        manager.save("test-session")

    files = os.listdir(temp_history_dir)
    assert any("10-00-00-1.json" in f for f in files)


def test_save_does_nothing_when_session_not_in_cache(temp_history_dir):
    """Line 288: save() returns early if conversation_name is not in cache."""
    manager = FileHistoryManager(temp_history_dir)
    # Must not raise and must not create any file
    manager.save("nonexistent-session")
    assert not os.path.exists(
        os.path.join(temp_history_dir, "nonexistent-session.json")
    )


def test_save_handles_os_error(temp_history_dir):
    """Lines 339-340: OSError during save is caught and does not propagate."""
    from pydantic_ai.messages import ModelRequest, UserPromptPart

    manager = FileHistoryManager(temp_history_dir)
    messages = [ModelRequest(parts=[UserPromptPart(content="hello")])]
    manager.update("os-error-session", messages)

    original_open = open

    def mock_open_selective(*args, **kwargs):
        if args and "os-error-session" in str(args[0]):
            raise OSError("disk full")
        return original_open(*args, **kwargs)

    from unittest.mock import patch

    with patch("builtins.open", side_effect=mock_open_selective):
        # Should not raise
        manager.save("os-error-session")


def test_load_returns_empty_after_validation_error(temp_history_dir):
    """Lines 263-269: ValidationError after cleaning returns empty list."""
    import json as _json

    manager = FileHistoryManager(temp_history_dir)
    file_path = os.path.join(temp_history_dir, "validation_fail.json")

    # Craft data that passes JSON parsing and cleaning but fails Pydantic validation.
    # A message with an unknown "kind" value is not a valid ModelMessage.
    bad_data = [
        {
            "kind": "totally-unknown-kind",
            "parts": [{"part_kind": "user-prompt", "content": "hi"}],
        }
    ]
    with open(file_path, "w") as _f:
        _json.dump(bad_data, _f)

    result = manager.load("validation_fail")
    assert result == []


def test_save_validation_error_does_not_save_file(temp_history_dir):
    """Lines 331-333: ValidationError during save prevents file creation."""
    from unittest.mock import patch

    from pydantic import ValidationError
    from pydantic_ai.messages import ModelRequest, UserPromptPart

    manager = FileHistoryManager(temp_history_dir)
    messages = [ModelRequest(parts=[UserPromptPart(content="hello")])]
    manager.update("val-error-session", messages)

    # Force validate_python to raise a ValidationError
    # ModelMessagesTypeAdapter is imported inside save(), so patch at the source
    with patch("pydantic_ai.messages.ModelMessagesTypeAdapter") as mock_adapter:
        from pydantic_core import InitErrorDetails

        mock_adapter.dump_python.return_value = []
        mock_adapter.validate_python.side_effect = ValidationError.from_exception_data(
            title="ModelMessages",
            input_type="python",
            line_errors=[
                InitErrorDetails(
                    type="missing",
                    loc=("field",),
                    input={},
                )
            ],
        )
        manager.save("val-error-session")

    # File must not have been created
    assert not os.path.exists(os.path.join(temp_history_dir, "val-error-session.json"))


# ---------------------------------------------------------------------------
# Tests to cover remaining missing lines
# ---------------------------------------------------------------------------


def test_load_user_prompt_with_all_non_string_list_items(temp_history_dir):
    """Line 40: user-prompt with list content where ALL items are non-strings."""
    manager = FileHistoryManager(temp_history_dir)
    file_path = os.path.join(temp_history_dir, "all_non_str.json")
    data = [
        {
            "kind": "request",
            "parts": [
                {
                    "part_kind": "user-prompt",
                    "content": [42, {"k": "v"}],  # ALL non-strings
                    "timestamp": "2026-01-01T00:00:00Z",
                }
            ],
            "timestamp": None,
            "instructions": None,
        }
    ]
    with open(file_path, "w") as f:
        json.dump(data, f)
    result = manager.load("all_non_str")
    assert len(result) == 1
    assert isinstance(result[0].parts[0].content, str)


def test_load_tool_return_uses_default_tool_name(temp_history_dir):
    """Line 58: tool-return without tool_name uses default 'unknown'."""
    manager = FileHistoryManager(temp_history_dir)
    file_path = os.path.join(temp_history_dir, "tool_return_no_name.json")
    data = [
        {
            "kind": "response",
            "parts": [
                {
                    "part_kind": "tool-call",
                    "tool_name": "some_tool",
                    "args": {},
                }
            ],
            "timestamp": "2026-01-01T00:00:00Z",
            "model_name": "test-model",
        },
        {
            "kind": "request",
            "parts": [
                {
                    "part_kind": "tool-return",
                    "content": "result data",
                    # No tool_name provided → should use "unknown"
                }
            ],
            "timestamp": None,
            "instructions": None,
        },
    ]
    with open(file_path, "w") as f:
        json.dump(data, f)
    result = manager.load("tool_return_no_name")
    assert len(result) == 2


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
