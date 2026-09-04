import json
import os

import pytest

from zrb.llm.history_manager.file_history_manager import FileHistoryManager


@pytest.fixture
def temp_history_dir(tmp_path):
    d = tmp_path / "history"
    d.mkdir()
    return str(d)


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


def test_save_write_backup_false_skips_backup_file(temp_history_dir):
    """A mid-turn checkpoint save (write_backup=False) writes the live file
    but no timestamped backup, regardless of LLM_HISTORY_BACKUP_RETAIN — a
    backup per tool call would spam the history dir for no benefit."""
    from pydantic_ai.messages import ModelRequest, UserPromptPart

    manager = FileHistoryManager(temp_history_dir)
    messages = [ModelRequest(parts=[UserPromptPart(content="hi")])]

    manager.update("test-session", messages)
    manager.save("test-session", write_backup=False)

    files = os.listdir(temp_history_dir)
    assert files == ["test-session.json"]


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
    mtime_before = manager.cache_sync_mtime("os-error-session")

    original_open = open

    def mock_open_selective(*args, **kwargs):
        if args and "os-error-session" in str(args[0]):
            raise OSError("disk full")
        return original_open(*args, **kwargs)

    from unittest.mock import patch

    with patch("builtins.open", side_effect=mock_open_selective):
        # Should not raise
        manager.save("os-error-session")

    # A failed write must not be recorded as a successful one: the entry stays
    # dirty (so it's never evicted, since eviction only drops clean entries)
    # and its mtime sync point stays where it was before the failed write.
    assert manager.is_dirty("os-error-session")
    assert manager.cache_sync_mtime("os-error-session") == mtime_before
    assert not os.path.exists(os.path.join(temp_history_dir, "os-error-session.json"))


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
    # ModelMessagesTypeAdapter is imported inside save() from zrb.llm.agent.types
    # (a re-export of pydantic_ai.messages.ModelMessagesTypeAdapter), so patch at
    # that source path, not the original pydantic_ai location — the re-export
    # already holds its own bound reference by the time save() imports it.
    with patch("zrb.llm.agent.types.ModelMessagesTypeAdapter") as mock_adapter:
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
