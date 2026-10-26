from pydantic_ai.messages import (
    ModelRequest,
    ModelResponse,
    SystemPromptPart,
    TextPart,
    ToolCallPart,
    UserPromptPart,
)

from zrb.llm.hook.turn_evidence import (
    turn_changed_paths,
    turn_states_preference,
    turn_wrote_files,
    user_turn_count,
)


class TestUserTurnCount:
    def test_counts_user_prompts_not_messages(self):
        "A ModelRequest also carries a system prompt and tool returns, so the"
        history = [
            ModelRequest(parts=[UserPromptPart(content="first")]),
            ModelResponse(parts=[TextPart(content="an answer")]),
            ModelRequest(parts=[UserPromptPart(content="second")]),
        ]
        assert user_turn_count(history) == 2

    def test_a_request_with_no_user_part_is_not_a_user_turn(self):
        history = [ModelRequest(parts=[SystemPromptPart(content="system only")])]
        assert user_turn_count(history) == 0

    def test_an_empty_history_is_zero(self):
        assert user_turn_count([]) == 0


class TestTurnChangedPaths:
    def test_collects_mutating_paths_in_order_without_duplicates(self):
        turn = [
            ModelResponse(
                parts=[
                    ToolCallPart(tool_name="Edit", args={"path": "a.py"}),
                    ToolCallPart(tool_name="Read", args={"path": "ignored.py"}),
                    ToolCallPart(tool_name="MV", args='{"src": "b.py", "dst": "c.py"}'),
                    ToolCallPart(tool_name="Write", args={"path": "a.py"}),
                ]
            )
        ]
        assert turn_changed_paths(turn) == ["a.py", "b.py", "c.py"]

    def test_skips_unparseable_arguments(self):
        turn = [
            ModelResponse(parts=[ToolCallPart(tool_name="Write", args="{not json")])
        ]
        assert turn_changed_paths(turn) == []


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
        "Only ModelResponse carries ToolCallPart; a stray one on a"
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
        "Multimodal content (a list of parts) is not scanned — the"
        turn = [ModelRequest(parts=[UserPromptPart(content=["please remember this"])])]
        assert turn_states_preference(turn) is False

    def test_ignores_assistant_text(self):
        "Only ModelRequest/UserPromptPart is scanned; a stray match in the"
        turn = [ModelResponse(parts=[TextPart(content="I prefer terse replies")])]
        assert turn_states_preference(turn) is False
