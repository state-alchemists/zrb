"``TranscriptPolicy`` — how a transcript is cut for a reader that acts on it."

from pydantic_ai.messages import (
    ModelRequest,
    ModelResponse,
    ThinkingPart,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)

from zrb.llm.contracts.util.history_formatter import (
    TranscriptPolicy,
    format_history_as_text,
)


def _one_return(content: str, tool_name: str) -> list:
    "A turn holding one tool return and the call it answers."
    return [
        ModelRequest(
            parts=[
                ToolReturnPart(
                    tool_name=tool_name,
                    content=content,
                    tool_call_id="c1",
                )
            ]
        )
    ]


class TestTranscriptPolicy:
    "Test ``TranscriptPolicy`` as ``format_history_as_text`` applies it."

    policy = TranscriptPolicy(
        tool_return_head_chars=100,
        tool_return_tail_chars=40,
        tool_return_keep=frozenset({"Remember"}),
        include_thinking=False,
    )

    def test_a_capped_return_keeps_both_ends_and_names_the_gap(self):
        "The head, the tail and the marker all survive the cut."
        content = "HEAD" + "x" * 500 + "TAIL"
        result = format_history_as_text(
            _one_return(content, "Shell"), full=True, policy=self.policy
        )
        head = self.policy.tool_return_head_chars or 0
        omitted = len(content) - head - self.policy.tool_return_tail_chars
        assert "HEAD" in result
        assert "TAIL" in result
        assert f"TRUNCATED {omitted} chars" in result

    def test_a_return_inside_the_cap_is_untouched(self):
        content = "HEAD" + "x" * 100 + "TAIL"
        result = format_history_as_text(
            _one_return(content, "Shell"), full=True, policy=self.policy
        )
        assert content in result
        assert "TRUNCATED" not in result

    def test_a_kept_tools_return_passes_through_whole(self):
        "A memory tool's return is what a claim is read out of; it is never cut."
        content = "HEAD" + "x" * 500 + "TAIL"
        result = format_history_as_text(
            _one_return(content, "Remember"), full=True, policy=self.policy
        )
        assert content in result
        assert "TRUNCATED" not in result

    def test_a_failed_return_is_never_capped(self):
        content = "HEAD" + "x" * 500 + "TAIL"
        messages = [
            ModelRequest(
                parts=[
                    ToolReturnPart(
                        tool_name="Shell",
                        content=content,
                        tool_call_id="c1",
                        outcome="failed",
                    )
                ]
            )
        ]
        result = format_history_as_text(messages, full=True, policy=self.policy)
        assert content in result
        assert "TRUNCATED" not in result

    def test_thinking_is_left_out_when_the_policy_says_so(self):
        messages = [
            ModelResponse(parts=[ThinkingPart(content="the writer's deliberation")]),
            ModelRequest(parts=[UserPromptPart(content="hi")]),
        ]
        capped = format_history_as_text(messages, full=True, policy=self.policy)
        whole = format_history_as_text(messages, full=True)

        assert "deliberation" not in capped
        assert "deliberation" in whole

    def test_a_capped_render_leaves_the_tool_call_arguments_alone(self):
        "The call is 1–11% of the prompt and the densest part of it."
        value = "x" * 200
        messages = [
            ModelResponse(
                parts=[
                    ToolCallPart(
                        tool_name="Read", args={"path": value}, tool_call_id="c1"
                    )
                ]
            )
        ]
        result = format_history_as_text(messages, full=True, policy=self.policy)
        assert value in result

    def test_without_a_policy_every_return_renders_whole(self):
        content = "HEAD" + "x" * 500 + "TAIL"
        result = format_history_as_text(_one_return(content, "Shell"), full=True)
        assert content in result
        assert "TRUNCATED" not in result
