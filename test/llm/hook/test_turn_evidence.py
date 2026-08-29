from pydantic_ai.messages import (
    ModelRequest,
    ModelResponse,
    TextPart,
    ToolCallPart,
    UserPromptPart,
)

from zrb.llm.hook.turn_evidence import turn_wrote_files


class TestTurnWroteFiles:
    def test_true_for_write_call(self):
        turn = [
            ModelResponse(
                parts=[ToolCallPart(tool_name="Write", args={}, tool_call_id="1")]
            )
        ]
        assert turn_wrote_files(turn) is True

    def test_true_for_edit_call(self):
        turn = [
            ModelResponse(
                parts=[ToolCallPart(tool_name="Edit", args={}, tool_call_id="1")]
            )
        ]
        assert turn_wrote_files(turn) is True

    def test_false_for_read_only_turn(self):
        turn = [
            ModelResponse(
                parts=[ToolCallPart(tool_name="Read", args={}, tool_call_id="1")]
            ),
            ModelResponse(parts=[TextPart(content="done")]),
        ]
        assert turn_wrote_files(turn) is False

    def test_false_for_empty_turn(self):
        assert turn_wrote_files([]) is False

    def test_ignores_tool_calls_in_requests(self):
        """Only ModelResponse carries ToolCallPart; a stray one on a
        ModelRequest (not how pydantic-ai shapes messages, but a defensive
        check) must not be mistaken for a match."""
        turn = [ModelRequest(parts=[UserPromptPart(content="hi")])]
        assert turn_wrote_files(turn) is False

    def test_custom_tool_names_override_default_set(self):
        turn = [
            ModelResponse(
                parts=[ToolCallPart(tool_name="Custom", args={}, tool_call_id="1")]
            )
        ]
        assert turn_wrote_files(turn) is False
        assert turn_wrote_files(turn, tool_names=frozenset({"Custom"})) is True
