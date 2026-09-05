from unittest.mock import MagicMock, patch

import pytest


class TestLoadCommandReplay:
    """Tests for /load rendering loaded history through live-message paths."""

    @pytest.fixture
    def recording_ui(self):
        """A SimpleUI subclass that records every append_to_output call."""
        from zrb.context.shared_context import SharedContext
        from zrb.llm.ui import SimpleUI, UIConfig

        class RecordingUI(SimpleUI):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.records: list[tuple[str, str]] = []

            def append_to_output(
                self, *values, sep=" ", end="\n", file=None, flush=False, kind="text"
            ):
                text = sep.join(str(v) for v in values) + end
                self.records.append((text, kind))

            async def print(self, text: str, kind: str = "text"):
                pass

            async def get_input(self, prompt: str) -> str:
                return ""

        return RecordingUI(
            ctx=SharedContext(),
            llm_task=MagicMock(),
            history_manager=MagicMock(),
            config=UIConfig.default(),
        )

    def test_load_renders_user_message_normally(self, recording_ui):
        """A loaded user prompt should appear with the same 💬 prefix as live."""
        from pydantic_ai.messages import ModelRequest, UserPromptPart

        ui = recording_ui
        ui.load_commands = ["/load"]
        ui.history_manager.load = MagicMock(
            return_value=[ModelRequest(parts=[UserPromptPart(content="hello there")])]
        )

        assert ui.handle_load_command("/load my-session") is True

        user_records = [r for r in ui.records if "💬" in r[0] and "hello there" in r[0]]
        assert len(user_records) == 1
        # User lines must render as normal text, not faint
        assert user_records[0][1] == "text"

    def test_load_renders_assistant_text_with_markdown(self, recording_ui):
        """A loaded assistant text should pass through render_markdown."""
        from pydantic_ai.messages import ModelResponse, TextPart

        ui = recording_ui
        ui.load_commands = ["/load"]
        ui.history_manager.load = MagicMock(
            return_value=[ModelResponse(parts=[TextPart(content="**bold reply**")])]
        )

        with patch(
            "zrb.llm.ui.base.ui.render_markdown",
            return_value="RENDERED MARKDOWN",
        ) as render:
            assert ui.handle_load_command("/load my-session") is True

        # Header for assistant should be emitted as normal text
        headers = [r for r in ui.records if "🤖" in r[0]]
        assert len(headers) == 1
        assert headers[0][1] == "text"

        # Markdown renderer must have been called with the assistant content
        render.assert_called_once()
        args, kwargs = render.call_args
        assert args[0] == "**bold reply**"

        # The rendered markdown output must reach the UI
        assert any("RENDERED MARKDOWN" in r[0] for r in ui.records)

    def test_load_renders_tool_call_with_faint_kind(self, recording_ui):
        """Tool calls in loaded history must render with the faint tool_call kind."""
        from pydantic_ai.messages import ModelResponse, ToolCallPart

        ui = recording_ui
        ui.load_commands = ["/load"]
        ui.history_manager.load = MagicMock(
            return_value=[
                ModelResponse(
                    parts=[
                        ToolCallPart(
                            tool_name="list_files",
                            args={"path": "."},
                            tool_call_id="call-1",
                        )
                    ]
                )
            ]
        )

        assert ui.handle_load_command("/load my-session") is True

        tool_records = [r for r in ui.records if "🧰" in r[0]]
        assert len(tool_records) == 1
        assert "list_files" in tool_records[0][0]
        assert "call-1" in tool_records[0][0]
        assert tool_records[0][1] == "tool_call"

    def test_load_renders_tool_return_with_faint_kind(self, recording_ui):
        """Tool returns in loaded history must render with the faint tool_call kind."""
        from pydantic_ai.messages import ModelRequest, ToolReturnPart

        ui = recording_ui
        ui.load_commands = ["/load"]
        ui.history_manager.load = MagicMock(
            return_value=[
                ModelRequest(
                    parts=[
                        ToolReturnPart(
                            tool_name="list_files",
                            content="a.py\nb.py",
                            tool_call_id="call-1",
                        )
                    ]
                )
            ]
        )

        assert ui.handle_load_command("/load my-session") is True

        return_records = [r for r in ui.records if "🔠" in r[0]]
        assert len(return_records) == 1
        assert "list_files" in return_records[0][0]
        assert "✅" in return_records[0][0]
        assert return_records[0][1] == "tool_call"
        # Body lines must also be faint
        body_records = [r for r in ui.records if r[0].strip() == "a.py"]
        assert body_records and body_records[0][1] == "tool_call"

    def test_load_empty_history_only_shows_switch_message(self, recording_ui):
        """Empty history should not emit any replay output, only the switch line."""
        ui = recording_ui
        ui.load_commands = ["/load"]
        ui.history_manager.load = MagicMock(return_value=[])

        assert ui.handle_load_command("/load my-session") is True

        # No user/assistant/tool lines
        assert not any("💬" in r[0] for r in ui.records)
        assert not any("🤖" in r[0] for r in ui.records)
        assert not any("🧰" in r[0] for r in ui.records)
        # The switch confirmation is still emitted
        assert any("switched" in r[0] for r in ui.records)

    def test_load_renders_thinking_with_thinking_kind(self, recording_ui):
        """Thinking parts in loaded history must render with the faint thinking kind."""
        from pydantic_ai.messages import ModelResponse, ThinkingPart

        ui = recording_ui
        ui.load_commands = ["/load"]
        ui.history_manager.load = MagicMock(
            return_value=[
                ModelResponse(parts=[ThinkingPart(content="pondering the question")])
            ]
        )

        assert ui.handle_load_command("/load my-session") is True

        thinking_records = [r for r in ui.records if "💭" in r[0]]
        assert len(thinking_records) == 1
        assert "pondering the question" in thinking_records[0][0]
        assert thinking_records[0][1] == "thinking"

    def test_load_renders_retry_prompt_with_faint_kind(self, recording_ui):
        """Retry-prompt parts in loaded history must render with the faint tool_call kind."""
        from pydantic_ai.messages import ModelRequest, RetryPromptPart

        ui = recording_ui
        ui.load_commands = ["/load"]
        ui.history_manager.load = MagicMock(
            return_value=[
                ModelRequest(
                    parts=[
                        RetryPromptPart(content="please use a valid argument"),
                    ]
                )
            ]
        )

        assert ui.handle_load_command("/load my-session") is True

        retry_records = [r for r in ui.records if "🔄" in r[0]]
        assert len(retry_records) == 1
        assert "please use a valid argument" in retry_records[0][0]
        assert retry_records[0][1] == "tool_call"

    def test_load_reports_history_manager_failure(self, recording_ui):
        """If the history manager raises, an error line must be shown to the user."""
        ui = recording_ui
        ui.load_commands = ["/load"]
        ui.history_manager.load = MagicMock(side_effect=RuntimeError("boom"))

        assert ui.handle_load_command("/load my-session") is True

        assert any("❌" in r[0] and "boom" in r[0] for r in ui.records)
