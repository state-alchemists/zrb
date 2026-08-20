from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestBaseUICommandHandlers:
    """Tests for BaseUI command handler methods."""

    @pytest.fixture
    def simple_ui_instance(self):
        """Create a SimpleUI instance for testing BaseUI methods."""
        from zrb.context.shared_context import SharedContext
        from zrb.llm.ui import SimpleUI, UIConfig

        class TestSimpleUI(SimpleUI):
            async def print(self, text: str, kind: str = "text"):
                pass

            async def get_input(self, prompt: str) -> str:
                return "test"

        ctx = SharedContext()
        return TestSimpleUI(
            ctx=ctx,
            llm_task=MagicMock(),
            history_manager=MagicMock(),
            config=UIConfig.default(),
        )

    def test_handle_exit_command(self, simple_ui_instance):
        """Test _handle_exit_command returns True for exit commands."""
        ui = simple_ui_instance
        ui.exit_commands = ["/exit", "/quit"]

        assert ui.handle_exit_command("/exit") is True
        assert ui.handle_exit_command("/quit") is True
        assert ui.handle_exit_command("/help") is False

    def test_handle_exit_command_trims_whitespace(self, simple_ui_instance):
        """Test _handle_exit_command trims whitespace."""
        ui = simple_ui_instance
        ui.exit_commands = ["/exit"]

        assert ui.handle_exit_command("  /exit  ") is True

    def test_handle_info_command(self, simple_ui_instance):
        """Test _handle_info_command returns True for info commands."""
        ui = simple_ui_instance
        ui.info_commands = ["/help", "/?"]
        ui.append_to_output = MagicMock()

        assert ui.handle_info_command("/help") is True
        ui.append_to_output.assert_called()

    def test_handle_info_command_empty_commands(self, simple_ui_instance):
        """Test _handle_info_command with empty commands list."""
        ui = simple_ui_instance
        ui.info_commands = []

        assert ui.handle_info_command("/help") is False

    def test_handle_save_command(self, simple_ui_instance):
        """Test _handle_save_command saves conversation."""
        ui = simple_ui_instance
        ui.save_commands = ["/save"]
        ui.history_manager.load = MagicMock(return_value=[])
        ui.history_manager.update = MagicMock()
        ui.history_manager.save = MagicMock()
        ui.append_to_output = MagicMock()
        ui.conversation_session_name = "test-session"

        result = ui.handle_save_command("/save my-save")

        assert result is True
        ui.history_manager.update.assert_called_once()
        ui.history_manager.save.assert_called_once_with("my-save")

    def test_handle_save_command_no_name(self, simple_ui_instance):
        """Test _handle_save_command with no name provided."""
        ui = simple_ui_instance
        ui.save_commands = ["/save"]
        ui.history_manager.load = MagicMock(return_value=[])
        ui.history_manager.update = MagicMock()

        result = ui.handle_save_command("/save")

        assert result is False

    def test_handle_save_command_handles_error(self, simple_ui_instance):
        """Test _handle_save_command handles history manager errors."""
        ui = simple_ui_instance
        ui.save_commands = ["/save"]
        ui.history_manager.load = MagicMock(side_effect=Exception("Load error"))
        ui.append_to_output = MagicMock()

        result = ui.handle_save_command("/save test")

        assert result is True  # Returns True because command matched
        ui.append_to_output.assert_called()  # Error was reported

    def test_handle_load_command(self, simple_ui_instance):
        """Test _handle_load_command loads conversation."""
        ui = simple_ui_instance
        ui.load_commands = ["/load"]
        ui.history_manager.load = MagicMock(return_value=[])
        ui.append_to_output = MagicMock()
        ui.accumulate_usage(MagicMock(input_tokens=100, output_tokens=50))

        result = ui.handle_load_command("/load my-session")

        assert result is True
        assert ui.conversation_session_name == "my-session"
        # The usage meter tracks spend per loaded conversation
        assert ui.session_token_usage == (0, 0)

    def test_handle_load_command_no_name(self, simple_ui_instance):
        """Test _handle_load_command with no name provided."""
        ui = simple_ui_instance
        ui.load_commands = ["/load"]

        result = ui.handle_load_command("/load")

        assert result is False

    # ── Item 4, Phase D: persona-swap-on-/load ──

    def test_load_ordinary_session_does_not_touch_persona(self, simple_ui_instance):
        """Loading a plain (non-delegated) session name, never having swapped
        away, must not touch the persona at all."""
        ui = simple_ui_instance
        ui.load_commands = ["/load"]
        ui.history_manager.load = MagicMock(return_value=[])

        with patch("zrb.llm.agent.subagent.manager.sub_agent_manager") as mock_manager:
            assert ui.handle_load_command("/load my-project-chat") is True

        mock_manager.get_agent_definition.assert_not_called()
        assert ui.active_subagent_persona is None

    def test_load_delegated_session_swaps_persona(self, simple_ui_instance):
        """Loading a delegated sub-agent's transcript must swap the running
        task's tools/toolsets/prompt_manager and the UI's model to match."""
        from zrb.llm.agent.subagent.manager import SubAgentDefinition

        ui = simple_ui_instance
        ui.load_commands = ["/load"]
        ui.history_manager.load = MagicMock(return_value=[])
        original_tools = ["original-tool"]
        original_toolsets = ["original-toolset"]
        original_prompt_manager = MagicMock()
        ui.llm_task.tools = original_tools
        ui.llm_task.toolsets = original_toolsets
        ui.llm_task.prompt_manager = original_prompt_manager
        ui.model = "main-model"

        definition = SubAgentDefinition(
            name="code-reviewer", path=".", description="d", system_prompt="p"
        )
        resolved = MagicMock(
            model="reviewer-model",
            system_prompt="You are a code reviewer.",
            tools=["reviewer-tool"],
            toolsets=["reviewer-toolset"],
        )

        with patch("zrb.llm.agent.subagent.manager.sub_agent_manager") as mock_manager:
            mock_manager.get_agent_definition.return_value = definition
            mock_manager.resolve_agent_build.return_value = resolved

            result = ui.handle_load_command("/load sess1-sub-code-reviewer-a1b2c3d4")

        assert result is True
        mock_manager.get_agent_definition.assert_called_once_with("code-reviewer")
        assert ui.llm_task.tools == ["reviewer-tool"]
        assert ui.llm_task.toolsets == ["reviewer-toolset"]
        assert ui.llm_task.prompt_manager is not original_prompt_manager
        assert ui.model == "reviewer-model"
        assert ui.active_subagent_persona == "code-reviewer"

    def test_load_delegated_session_unknown_agent_reports_error(
        self, simple_ui_instance
    ):
        """An unresolvable agent must not silently swap — report and stay on
        the main agent."""
        ui = simple_ui_instance
        ui.load_commands = ["/load"]
        ui.history_manager.load = MagicMock(return_value=[])
        ui.append_to_output = MagicMock()

        with patch("zrb.llm.agent.subagent.manager.sub_agent_manager") as mock_manager:
            mock_manager.get_agent_definition.return_value = None
            result = ui.handle_load_command("/load sess1-sub-ghost-agent-deadbeef")

        assert result is True
        assert ui.active_subagent_persona is None
        assert any(
            "ghost-agent" in str(call) for call in ui.append_to_output.call_args_list
        )

    def test_load_back_to_ordinary_session_restores_main_persona(
        self, simple_ui_instance
    ):
        """/load-ing back to an ordinary session name after a swap restores
        the original (main-agent) tools/toolsets/prompt_manager/model."""
        from zrb.llm.agent.subagent.manager import SubAgentDefinition

        ui = simple_ui_instance
        ui.load_commands = ["/load"]
        ui.history_manager.load = MagicMock(return_value=[])
        original_tools = ["original-tool"]
        original_toolsets = ["original-toolset"]
        original_prompt_manager = MagicMock()
        ui.llm_task.tools = original_tools
        ui.llm_task.toolsets = original_toolsets
        ui.llm_task.prompt_manager = original_prompt_manager
        ui.model = "main-model"

        definition = SubAgentDefinition(
            name="researcher", path=".", description="d", system_prompt="p"
        )
        resolved = MagicMock(
            model="researcher-model",
            system_prompt="You research.",
            tools=["researcher-tool"],
            toolsets=["researcher-toolset"],
        )

        with patch("zrb.llm.agent.subagent.manager.sub_agent_manager") as mock_manager:
            mock_manager.get_agent_definition.return_value = definition
            mock_manager.resolve_agent_build.return_value = resolved
            ui.handle_load_command("/load sess1-sub-researcher-deadbeef")

            result = ui.handle_load_command("/load my-project-chat")

        assert result is True
        assert ui.llm_task.tools == original_tools
        assert ui.llm_task.toolsets == original_toolsets
        assert ui.llm_task.prompt_manager is original_prompt_manager
        assert ui.model == "main-model"
        assert ui.active_subagent_persona is None

    def test_load_second_subagent_keeps_the_original_main_snapshot(
        self, simple_ui_instance
    ):
        """Swapping A -> B must restore the ORIGINAL main persona when going
        back, not B's persona re-labeled as "main"."""
        from zrb.llm.agent.subagent.manager import SubAgentDefinition

        ui = simple_ui_instance
        ui.load_commands = ["/load"]
        ui.history_manager.load = MagicMock(return_value=[])
        original_tools = ["original-tool"]
        ui.llm_task.tools = original_tools
        ui.llm_task.toolsets = []
        ui.llm_task.prompt_manager = MagicMock()
        ui.model = "main-model"

        def make_definition(name):
            return SubAgentDefinition(
                name=name, path=".", description="d", system_prompt="p"
            )

        with patch("zrb.llm.agent.subagent.manager.sub_agent_manager") as mock_manager:
            mock_manager.get_agent_definition.side_effect = (
                lambda name: make_definition(name)
            )
            mock_manager.resolve_agent_build.side_effect = lambda definition, **_: (
                MagicMock(
                    model=f"{definition.name}-model",
                    system_prompt=f"You are {definition.name}.",
                    tools=[f"{definition.name}-tool"],
                    toolsets=[],
                )
            )

            ui.handle_load_command("/load sess1-sub-researcher-deadbeef")
            ui.handle_load_command("/load sess1-sub-code-reviewer-a1b2c3d4")
            ui.handle_load_command("/load my-project-chat")

        assert ui.llm_task.tools == original_tools
        assert ui.model == "main-model"
        assert ui.active_subagent_persona is None

    def test_handle_redirect_command(self, simple_ui_instance):
        """Test _handle_redirect_command redirects output to file."""
        import os
        import tempfile

        ui = simple_ui_instance
        ui.redirect_output_commands = ["/redirect"]
        ui.last_result_data = "Test output content"
        ui.append_to_output = MagicMock()

        with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as f:
            temp_path = f.name

        try:
            result = ui.handle_redirect_command(f"/redirect {temp_path}")

            assert result is True
            with open(temp_path, "r") as f:
                assert f.read() == "Test output content"
        finally:
            os.unlink(temp_path)

    def test_handle_redirect_command_no_output(self, simple_ui_instance):
        """Test _handle_redirect_command when no output available."""
        ui = simple_ui_instance
        ui.redirect_output_commands = ["/redirect"]
        ui.last_result_data = None
        ui.append_to_output = MagicMock()

        result = ui.handle_redirect_command("/redirect /tmp/out.txt")

        assert result is True
        ui.append_to_output.assert_called()  # Error message shown

    def test_handle_redirect_command_clipboard(self, simple_ui_instance):
        """Test _handle_redirect_command bare command copies output to clipboard."""
        from unittest.mock import patch

        ui = simple_ui_instance
        ui.redirect_output_commands = ["/redirect"]
        ui.last_result_data = "Test AI output"
        ui.append_to_output = MagicMock()

        with patch("zrb.llm.util.clipboard.copy_text", return_value=True) as mock_copy:
            result = ui.handle_redirect_command("/redirect")

        assert result is True
        mock_copy.assert_called_once_with("Test AI output")

    def test_handle_redirect_command_bare_no_output(self, simple_ui_instance):
        """Test bare /redirect shows error when no output available."""
        from unittest.mock import patch

        ui = simple_ui_instance
        ui.redirect_output_commands = ["/redirect"]
        ui.last_result_data = None
        ui.append_to_output = MagicMock()

        with patch("zrb.llm.util.clipboard.copy_text") as mock_copy:
            result = ui.handle_redirect_command("/redirect")

        assert result is True
        mock_copy.assert_not_called()
        ui.append_to_output.assert_called()  # Error shown

    # --- copy command --------------------------------------------------------

    def test_handle_copy_command(self, simple_ui_instance):
        """Test bare /copy copies full transcript to clipboard."""
        from unittest.mock import patch

        ui = simple_ui_instance
        ui.copy_commands = ["/copy"]
        ui.history_manager.load = MagicMock(
            return_value=[{"role": "user", "content": "hi"}]
        )
        ui.append_to_output = MagicMock()

        with patch("zrb.llm.util.clipboard.copy_text", return_value=True) as mock_copy:
            with patch(
                "zrb.llm.util.history_formatter.format_history_as_text",
                return_value="transcript",
            ):
                result = ui.handle_copy_command("/copy")

        assert result is True
        mock_copy.assert_called_once_with("transcript")

    def test_handle_copy_command_to_file(self, simple_ui_instance):
        """Test /copy with path writes transcript to file."""
        import os
        import tempfile

        ui = simple_ui_instance
        ui.copy_commands = ["/copy"]
        ui.history_manager.load = MagicMock(
            return_value=[{"role": "user", "content": "hi"}]
        )
        ui.append_to_output = MagicMock()

        with patch(
            "zrb.llm.util.history_formatter.format_history_as_text",
            return_value="transcript content",
        ):
            with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as f:
                temp_path = f.name

            try:
                result = ui.handle_copy_command(f"/copy {temp_path}")
                assert result is True
                with open(temp_path) as f:
                    assert f.read() == "transcript content"
            finally:
                os.unlink(temp_path)

    def test_handle_copy_command_no_history(self, simple_ui_instance):
        """Test /copy shows error when no history."""
        ui = simple_ui_instance
        ui.copy_commands = ["/copy"]
        ui.history_manager.load = MagicMock(return_value=[])
        ui.append_to_output = MagicMock()

        result = ui.handle_copy_command("/copy")

        assert result is True
        ui.append_to_output.assert_called()  # Error shown

    def test_handle_copy_command_trailing_space_strips_to_bare(
        self, simple_ui_instance
    ):
        """Test /copy with a trailing space strips to the bare command (clipboard copy)."""
        ui = simple_ui_instance
        ui.copy_commands = ["/copy"]
        ui.history_manager.load = MagicMock(return_value=[])
        ui.append_to_output = MagicMock()

        result = ui.handle_copy_command("/copy ")

        assert result is True  # stripped to bare /copy

    def test_handle_copy_command_unrecognized(self, simple_ui_instance):
        """Test /copy with an unrecognized command returns False."""
        ui = simple_ui_instance
        ui.copy_commands = ["/copy"]

        result = ui.handle_copy_command("/notcopy")

        assert result is False

    def test_handle_toggle_yolo(self, simple_ui_instance):
        """Test _handle_toggle_yolo toggles yolo mode."""
        ui = simple_ui_instance

        assert ui.yolo is False
        ui.handle_toggle_yolo("/yolo")
        assert ui.yolo is True
        ui.handle_toggle_yolo("/yolo")
        assert ui.yolo is False

    def test_handle_set_model_command(self, simple_ui_instance):
        """Test _handle_set_model_command changes model."""
        ui = simple_ui_instance
        ui.set_model_commands = ["/model"]
        ui.is_thinking = False
        ui.append_to_output = MagicMock()

        result = ui.handle_set_model_command("/model gpt-4")

        assert result is True
        assert ui.model == "gpt-4"

    def test_handle_set_model_command_while_thinking(self, simple_ui_instance):
        """Test _handle_set_model_command blocked while thinking."""
        ui = simple_ui_instance
        ui.set_model_commands = ["/model"]
        ui.is_thinking = True

        result = ui.handle_set_model_command("/model gpt-4")

        assert result is False

    def test_handle_set_model_command_no_model(self, simple_ui_instance):
        """Test _handle_set_model_command with no model provided."""
        ui = simple_ui_instance
        ui.set_model_commands = ["/model"]
        ui.is_thinking = False

        result = ui.handle_set_model_command("/model")

        assert result is False

    def test_handle_attach_command(self, simple_ui_instance):
        """Test _handle_attach_command attaches file."""
        import os
        import tempfile

        ui = simple_ui_instance
        ui.attach_commands = ["/attach"]
        ui.append_to_output = MagicMock()

        # Create a temp file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as f:
            f.write(b"test")
            temp_path = f.name

        try:
            result = ui.handle_attach_command(f"/attach {temp_path}")

            assert result is True
            assert temp_path in ui.pending_attachments
        finally:
            os.unlink(temp_path)

    def test_handle_attach_command_file_not_found(self, simple_ui_instance):
        """Test _handle_attach_command with non-existent file."""
        ui = simple_ui_instance
        ui.attach_commands = ["/attach"]
        ui.append_to_output = MagicMock()

        result = ui.handle_attach_command("/attach /nonexistent/file.txt")

        assert result is True
        ui.append_to_output.assert_called()  # Error shown

    def test_handle_attach_command_already_attached(self, simple_ui_instance):
        """Test _handle_attach_command with already attached file."""
        import os
        import tempfile

        ui = simple_ui_instance
        ui.attach_commands = ["/attach"]
        ui.append_to_output = MagicMock()

        with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as f:
            f.write(b"test")
            temp_path = f.name

        try:
            # Attach first time
            ui.handle_attach_command(f"/attach {temp_path}")
            # Try to attach again
            ui.append_to_output.reset_mock()
            result = ui.handle_attach_command(f"/attach {temp_path}")

            assert result is True
            ui.append_to_output.assert_called()  # "Already attached" message
        finally:
            os.unlink(temp_path)

    @pytest.mark.asyncio
    async def test_handle_photo_command_captures_and_attaches(self, simple_ui_instance):
        """Test _handle_photo_command captures a photo and attaches it."""
        ui = simple_ui_instance
        ui.photo_commands = ["/photo"]
        ui.append_to_output = MagicMock()

        with patch(
            "zrb.llm.ui.base.conversation_commands.get_camera_photo",
            new=AsyncMock(return_value=b"\xff\xd8\xff-fake-jpeg"),
        ):
            result = ui.handle_photo_command("/photo")

            assert result is True
            assert len(ui.background_tasks) == 1
            task = list(ui.background_tasks)[0]
            await task

        assert len(ui.pending_attachments) == 1

    @pytest.mark.asyncio
    async def test_handle_photo_command_capture_failure(self, simple_ui_instance):
        """Test _handle_photo_command shows an error when capture fails."""
        ui = simple_ui_instance
        ui.photo_commands = ["/photo"]
        ui.append_to_output = MagicMock()

        with patch(
            "zrb.llm.ui.base.conversation_commands.get_camera_photo",
            new=AsyncMock(return_value=None),
        ):
            result = ui.handle_photo_command("/photo")

            task = list(ui.background_tasks)[0]
            await task

        assert result is True
        assert ui.pending_attachments == []
        ui.append_to_output.assert_called()

    def test_get_help_text(self, simple_ui_instance):
        """Test _get_help_text returns formatted help."""
        ui = simple_ui_instance
        ui.exit_commands = ["/exit"]
        ui.info_commands = ["/help"]
        ui.attach_commands = ["/attach"]

        help_text = ui.get_help_text()

        assert "/exit" in help_text
        assert "/help" in help_text
        assert "/attach" in help_text
        assert "Keyboard Shortcuts:" in help_text
        assert "Ctrl+J" in help_text
        assert "Ctrl+V / Alt+V" in help_text
        assert "Ctrl+K" in help_text
        assert "Shift+Tab" in help_text

    def test_get_help_text_lists_every_command_at_any_width(self, simple_ui_instance):
        """No command is dropped and no description clipped, however narrow."""
        ui = simple_ui_instance
        ui.exit_commands = ["/exit"]
        ui.info_commands = ["/help"]
        ui.attach_commands = ["/attach"]

        for width in (200, 100, 50):
            help_text = ui.get_help_text(width=width)
            assert "and more" not in help_text
            assert "..." not in help_text
            for expected in ("/exit", "/help", "/attach", "clipboard"):
                assert expected in help_text

    def test_get_help_text_empty_commands(self, simple_ui_instance):
        """Test _get_help_text with all empty command lists."""
        ui = simple_ui_instance
        ui.exit_commands = []
        ui.info_commands = []
        ui.attach_commands = []
        ui.photo_commands = []
        ui.save_commands = []
        ui.load_commands = []
        ui.redirect_output_commands = []
        ui.summarize_commands = []
        ui.yolo_toggle_commands = []
        ui.set_model_commands = []
        ui.exec_commands = []
        ui.plan_commands = []
        ui.copy_commands = []
        ui.custom_commands = []

        help_text = ui.get_help_text()

        assert help_text == ""

    def test_get_cwd_display_home(self, simple_ui_instance, monkeypatch):
        """Test get_cwd_display shows home directory as ~."""
        ui = simple_ui_instance

        import os

        # monkeypatch restores the original cwd on teardown — an unrestored
        # os.chdir() here would leak into every test that runs afterward,
        # depending on collection order to avoid ever being noticed.
        monkeypatch.chdir(os.path.expanduser("~"))

        result = ui.get_cwd_display()

        assert result == "~"

    def test_execute_hook_sync_context(self, simple_ui_instance):
        """Test execute_hook works in sync context."""
        from zrb.llm.hook.types import HookEvent

        ui = simple_ui_instance

        # Should not raise even without running event loop
        ui.execute_hook(HookEvent.NOTIFICATION, {"message": "test"})

    def test_triggers_property(self, simple_ui_instance):
        """Test triggers property getter and setter."""
        ui = simple_ui_instance

        async def trigger():
            yield "triggered"

        ui.triggers = [trigger]

        assert trigger in ui.triggers

    def test_invalidate_ui(self, simple_ui_instance):
        """Test invalidate_ui does not raise."""
        ui = simple_ui_instance

        # Should not raise
        ui.invalidate_ui()

    def test_on_exit(self, simple_ui_instance):
        """Test on_exit does not raise."""
        ui = simple_ui_instance

        # Should not raise
        ui.on_exit()

    def test_get_output_field_width(self, simple_ui_instance):
        """Test _get_output_field_width returns None by default."""
        ui = simple_ui_instance

        assert ui._get_output_field_width() is None

    def test_stream_to_parent(self, simple_ui_instance):
        """Test stream_to_parent calls append_to_output."""
        ui = simple_ui_instance
        ui.append_to_output = MagicMock()

        ui.stream_to_parent("test output")

        ui.append_to_output.assert_called_once()


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
