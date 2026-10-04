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


def test_strips_trailing_live_context_from_a_string_prompt():
    messages = [
        ModelRequest(
            parts=[
                UserPromptPart(
                    content=(
                        "what changed\n\n"
                        "<live-context>- Time: 2024-01-01 00:00:00 UTC (+0000)"
                        "</live-context>"
                    )
                )
            ]
        ),
    ]
    assert extract_user_message_texts(messages) == ["what changed"]


def test_strips_trailing_live_context_item_from_a_multimodal_prompt():
    from pydantic_ai.messages import ImageUrl

    messages = [
        ModelRequest(
            parts=[
                UserPromptPart(
                    content=[
                        "look at this",
                        ImageUrl(url="http://x/y.png"),
                        "<live-context>- Time: now</live-context>",
                    ]
                )
            ]
        ),
    ]
    assert extract_user_message_texts(messages) == [
        "look at this [Image URL: http://x/y.png]"
    ]
