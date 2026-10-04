"""`extract_user_message_texts`, the history-formatter helper the input box's
previous-message recall uses to recover a loaded conversation's user turns."""

from pydantic_ai.messages import (
    ModelRequest,
    ModelResponse,
    TextPart,
    ToolReturnPart,
    UserPromptPart,
)

from zrb.llm.util.history_formatter import extract_user_message_texts


def test_empty():
    assert extract_user_message_texts([]) == []


def test_returns_user_prompts_newest_first():
    messages = [
        ModelRequest(parts=[UserPromptPart(content="first")]),
        ModelResponse(parts=[TextPart(content="reply")]),
        ModelRequest(parts=[UserPromptPart(content="second")]),
    ]
    assert extract_user_message_texts(messages) == ["second", "first"]


def test_skips_non_user_parts_and_responses():
    messages = [
        ModelRequest(
            parts=[
                ToolReturnPart(
                    tool_name="list_files",
                    content="a.py",
                    tool_call_id="call-1",
                )
            ]
        ),
        ModelResponse(parts=[TextPart(content="reply")]),
        ModelRequest(parts=[UserPromptPart(content="typed")]),
    ]
    assert extract_user_message_texts(messages) == ["typed"]


def test_skips_blank_user_prompts():
    messages = [
        ModelRequest(parts=[UserPromptPart(content="   ")]),
        ModelRequest(parts=[UserPromptPart(content="real")]),
    ]
    assert extract_user_message_texts(messages) == ["real"]
