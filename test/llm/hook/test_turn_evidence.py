from pydantic_ai.messages import (
    ModelRequest,
    ModelResponse,
    TextPart,
    ToolCallPart,
    UserPromptPart,
)

from zrb.llm.hook.turn_evidence import turn_states_preference, turn_wrote_files


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


class TestTurnStatesPreference:
    def test_true_for_i_prefer(self):
        turn = [ModelRequest(parts=[UserPromptPart(content="I prefer terse replies")])]
        assert turn_states_preference(turn) is True

    def test_true_case_insensitive(self):
        turn = [ModelRequest(parts=[UserPromptPart(content="FROM NOW ON use tabs")])]
        assert turn_states_preference(turn) is True

    def test_false_for_ordinary_question(self):
        turn = [ModelRequest(parts=[UserPromptPart(content="what does this do?")])]
        assert turn_states_preference(turn) is False

    def test_false_for_empty_turn(self):
        assert turn_states_preference([]) is False

    def test_ignores_non_string_content(self):
        """Multimodal content (a list of parts) is not scanned — the
        heuristic only ever looks at plain text."""
        turn = [ModelRequest(parts=[UserPromptPart(content=["please remember this"])])]
        assert turn_states_preference(turn) is False

    def test_ignores_assistant_text(self):
        """Only ModelRequest/UserPromptPart is scanned; a stray match in the
        assistant's own output must not count."""
        turn = [ModelResponse(parts=[TextPart(content="I prefer terse replies")])]
        assert turn_states_preference(turn) is False
