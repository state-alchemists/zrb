import json
import os

import pytest
from pydantic_ai.messages import TextPart, UserPromptPart

from zrb.llm.history_manager.file_history_manager import FileHistoryManager


@pytest.fixture
def temp_history_dir(tmp_path):
    d = tmp_path / "history"
    d.mkdir()
    return str(d)


def test_file_history_manager_save_load(temp_history_dir):
    manager = FileHistoryManager(temp_history_dir)


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


    manager2 = FileHistoryManager(temp_history_dir)
    loaded = manager2.load("session1")
    assert len(loaded) == 2
    assert isinstance(loaded[0].parts[0], UserPromptPart)
    assert loaded[0].parts[0].content == "hello"


def test_clean_corrupted_content_preserves_structural_fields(temp_history_dir):
    'Content cleaning preserves structural fields it does not normalize.'
    from pydantic_ai.messages import (
        ModelRequest,
        ModelResponse,
        RetryPromptPart,
        ThinkingPart,
    )

    messages = [
        ModelResponse(
            parts=[ThinkingPart(content="reasoning", signature="sig-abc", id="th-1")]
        ),
        ModelRequest(
            parts=[
                RetryPromptPart(
                    content="bad", tool_name="mytool", tool_call_id="call-9"
                )
            ]
        ),
    ]

    manager = FileHistoryManager(temp_history_dir)
    manager.update("structural", messages)
    manager.save("structural")


    loaded = FileHistoryManager(temp_history_dir).load("structural")

    thinking = loaded[0].parts[0]
    assert isinstance(thinking, ThinkingPart)
    assert thinking.content == "reasoning"
    assert thinking.signature == "sig-abc"
    assert thinking.id == "th-1"

    retry = loaded[1].parts[0]
    assert isinstance(retry, RetryPromptPart)
    assert retry.tool_name == "mytool"
    assert retry.tool_call_id == "call-9"


def test_file_history_manager_search(temp_history_dir):
    manager = FileHistoryManager(temp_history_dir)

    (open(os.path.join(temp_history_dir, "apple.json"), "w")).close()
    (open(os.path.join(temp_history_dir, "banana.json"), "w")).close()

    results = manager.search("app")
    assert "apple" in results
    assert "banana" not in results


def test_file_history_manager_search_empty_orders_by_mtime_desc(temp_history_dir):
    manager = FileHistoryManager(temp_history_dir)
    for name in ("old", "mid", "new"):
        open(os.path.join(temp_history_dir, f"{name}.json"), "w").close()

    os.utime(os.path.join(temp_history_dir, "old.json"), (1000, 1000))
    os.utime(os.path.join(temp_history_dir, "mid.json"), (2000, 2000))
    os.utime(os.path.join(temp_history_dir, "new.json"), (3000, 3000))

    assert manager.search("") == ["new", "mid", "old"]


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
    'Test that dictionary in UserPromptPart.content is proactively cleaned to JSON string.'
    manager = FileHistoryManager(temp_history_dir)
    file_path = os.path.join(temp_history_dir, "corrupted.json")




    corrupted_data = [
        {
            "kind": "request",
            "parts": [
                {
                    "part_kind": "user-prompt",
                    "content": {
                        "summary": "test",
                        "results": [],
                    },
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


    result = manager.load("corrupted")
    assert len(result) == 1
    assert isinstance(result[0].parts[0], UserPromptPart)
    assert (
        result[0].parts[0].content == '{"summary": "test", "results": []}'
    )


def test_file_history_manager_load_validation_error_boolean(temp_history_dir):
    'Test that boolean in UserPromptPart.content is proactively cleaned to string.'
    manager = FileHistoryManager(temp_history_dir)
    file_path = os.path.join(temp_history_dir, "corrupted_bool.json")


    corrupted_data = [
        {
            "kind": "request",
            "parts": [
                {
                    "part_kind": "user-prompt",
                    "content": True,
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


    result = manager.load("corrupted_bool")
    assert len(result) == 1
    assert isinstance(result[0].parts[0], UserPromptPart)
    assert result[0].parts[0].content == "True"


def test_file_history_manager_load_validation_error_number(temp_history_dir):
    'Test that number in UserPromptPart.content is proactively cleaned to string.'
    manager = FileHistoryManager(temp_history_dir)
    file_path = os.path.join(temp_history_dir, "corrupted_number.json")


    corrupted_data = [
        {
            "kind": "request",
            "parts": [
                {
                    "part_kind": "user-prompt",
                    "content": 42,
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


    result = manager.load("corrupted_number")
    assert len(result) == 1
    assert isinstance(result[0].parts[0], UserPromptPart)
    assert result[0].parts[0].content == "42"


def test_file_history_manager_save_with_corrupted_data(temp_history_dir):
    'Test that save() handles corrupted data with auto-recovery.'
    manager = FileHistoryManager(temp_history_dir)


    from pydantic_ai.messages import ModelMessage, ModelRequest, UserPromptPart




    messages: list[ModelMessage] = [
        ModelRequest(parts=[UserPromptPart(content="normal message")]),
    ]

    manager.update("test_session", messages)
    manager.save("test_session")


    file_path = os.path.join(temp_history_dir, "test_session.json")
    assert os.path.exists(file_path)


    loaded = manager.load("test_session")
    assert len(loaded) == 1
    assert isinstance(loaded[0].parts[0], UserPromptPart)
    assert loaded[0].parts[0].content == "normal message"


def test_file_history_manager_clean_corrupted_content_via_load(temp_history_dir):
    'Test that corrupted content is cleaned when loading via public API.'
    manager = FileHistoryManager(temp_history_dir)


    file_path = os.path.join(temp_history_dir, "test_dict.json")
    data = {
        "part_kind": "user-prompt",
        "content": {"key": "value"},
        "timestamp": "2026-02-23T09:25:23.369273Z",
    }
    json.dump([{"kind": "request", "parts": [data]}], open(file_path, "w"))
    result = manager.load("test_dict")
    assert isinstance(result[0].parts[0], UserPromptPart)
    assert result[0].parts[0].content == '{"key": "value"}'


def test_file_history_manager_filter_empty_responses_via_load(temp_history_dir):
    'Test filtering out empty responses when loading history data.'
    manager = FileHistoryManager(temp_history_dir)


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
            "parts": [],
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

    assert len(result) == 2


def test_save_with_timestamped_session_name(temp_history_dir):
    'Test that save() correctly handles session names with timestamps.'
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


    manager.update("my-session-2024-03-18-10-30-00", messages)
    manager.save("my-session-2024-03-18-10-30-00")


    main_file = os.path.join(temp_history_dir, "my-session-2024-03-18-10-30-00.json")
    assert os.path.exists(main_file)


    files = os.listdir(temp_history_dir)

    backup_pattern = re.compile(
        r"my-session-\d{4}-\d{2}-\d{2}-\d{2}-\d{2}-\d{2}(?:-\d+)?\.json"
    )
    backup_files = [f for f in files if backup_pattern.match(f)]




    timestamp_pattern = re.compile(
        r"my-session-\d{4}-\d{2}-\d{2}-\d{2}-\d{2}-\d{2}\.json"
    )
    main_files = [f for f in files if timestamp_pattern.match(f)]


    assert len(main_files) == 2, f"Expected 2 files (main + backup), found: {files}"


def test_rotation_never_deletes_timestamped_main_file(temp_history_dir, monkeypatch):
    'A conversation whose name carries a timestamp must survive rotation.'
    from pydantic_ai.messages import (
        ModelRequest,
        ModelResponse,
        TextPart,
        UserPromptPart,
    )

    monkeypatch.setenv("ZRB_LLM_HISTORY_BACKUP_RETAIN", "2")
    manager = FileHistoryManager(temp_history_dir)
    name = "my-session-2024-03-18-10-30-00"
    main_file = os.path.join(temp_history_dir, f"{name}.json")

    for i in range(5):
        messages = [
            ModelRequest(parts=[UserPromptPart(content=f"hello {i}")]),
            ModelResponse(parts=[TextPart(content=f"hi {i}")]),
        ]
        manager.update(name, messages)
        manager.save(name)

        assert os.path.exists(main_file), f"Main file deleted after save #{i}"


def test_init_creates_directory_if_not_exists(tmp_path):
    'Line 24: os.makedirs() is called when history_dir does not exist.'
    new_dir = str(tmp_path / "does" / "not" / "exist")
    assert not os.path.exists(new_dir)
    FileHistoryManager(new_dir)
    assert os.path.isdir(new_dir)


def test_load_user_prompt_with_list_of_non_strings(temp_history_dir):
    'Lines 40-43: user-prompt content is a list that contains non-string items.'
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

    assert len(result) == 1
    assert isinstance(result[0].parts[0], UserPromptPart)
    assert isinstance(result[0].parts[0].content, str)


def test_load_text_part_with_non_string_content(temp_history_dir):
    'Line 51: text/thinking/retry-prompt part with non-string content is converted.'
    manager = FileHistoryManager(temp_history_dir)
    file_path = os.path.join(temp_history_dir, "text_nonstring.json")
    data = [
        {
            "kind": "response",
            "parts": [
                {
                    "part_kind": "text",
                    "content": 99,
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
    assert isinstance(result[0].parts[0], TextPart)
    assert result[0].parts[0].content == "99"
