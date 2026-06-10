"""Tests for StdUI class."""

from io import StringIO
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from zrb.llm.ui.std_ui import (
    _FREE_TEXT,
    StdUI,
    _option_text,
    resolve_choice_selection,
)


def test_stdui_append_to_output():
    """Test StdUI append_to_output writes to stderr."""
    ui = StdUI()

    with patch("sys.stderr", new_callable=StringIO) as mock_stderr:
        ui.append_to_output("Hello", "World", sep="-", end="!")
        output = mock_stderr.getvalue()
        assert output == "Hello-World!"


def test_stdui_append_to_output_with_flush():
    """Test StdUI append_to_output with flush=True."""
    ui = StdUI()

    with patch("sys.stderr", new_callable=StringIO) as mock_stderr:
        ui.append_to_output("Test", flush=True)
        output = mock_stderr.getvalue()
        assert output == "Test\n"


def test_stdui_append_to_output_multiple_values():
    """Test StdUI append_to_output with multiple values."""
    ui = StdUI()

    with patch("sys.stderr", new_callable=StringIO) as mock_stderr:
        ui.append_to_output("Line 1", "Line 2", "Line 3", sep="\n")
        output = mock_stderr.getvalue()
        assert output == "Line 1\nLine 2\nLine 3\n"


@pytest.mark.asyncio
async def test_stdui_run_interactive_command():
    """Test StdUI run_interactive_command runs subprocess."""
    ui = StdUI()

    # Mock subprocess.run to avoid actual execution
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        result = await ui.run_interactive_command(["echo", "test"])

        mock_run.assert_called_once_with(["echo", "test"], shell=False)
        assert result.returncode == 0


@pytest.mark.asyncio
async def test_stdui_run_interactive_command_with_shell():
    """Test StdUI run_interactive_command with shell=True."""
    ui = StdUI()

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        result = await ui.run_interactive_command("echo test", shell=True)

        mock_run.assert_called_once_with("echo test", shell=True)
        assert result.returncode == 0


@pytest.mark.asyncio
async def test_stdui_run_interactive_command_string():
    """Test StdUI run_interactive_command with string command."""
    ui = StdUI()

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        await ui.run_interactive_command("ls -la", shell=True)

        mock_run.assert_called_once_with("ls -la", shell=True)


@pytest.mark.asyncio
async def test_stdui_ask_user_success():
    """Test StdUI ask_user returns user input."""
    ui = StdUI()

    # Patch PromptSession at the prompt_toolkit module level
    with patch("prompt_toolkit.PromptSession", create=True) as mock_session_class:
        mock_session = MagicMock()
        mock_session.prompt_async = AsyncMock(return_value="user input  ")
        mock_session_class.return_value = mock_session

        with patch("prompt_toolkit.output.create_output") as mock_create_output:
            mock_create_output.return_value = MagicMock()

            result = await ui.ask_user("Enter something: ")

            assert result == "user input"


@pytest.mark.asyncio
async def test_stdui_ask_user_eof():
    """Test StdUI ask_user handles EOFError."""
    ui = StdUI()

    with patch("prompt_toolkit.PromptSession", create=True) as mock_session_class:
        mock_session = MagicMock()
        mock_session.prompt_async = AsyncMock(side_effect=EOFError())
        mock_session_class.return_value = mock_session

        with patch("prompt_toolkit.output.create_output") as mock_create_output:
            mock_create_output.return_value = MagicMock()

            result = await ui.ask_user("Enter something: ")

            assert result == ""


@pytest.mark.asyncio
async def test_stdui_ask_user_keyboard_interrupt():
    """Test StdUI ask_user propagates KeyboardInterrupt."""
    ui = StdUI()

    with patch("prompt_toolkit.PromptSession", create=True) as mock_session_class:
        mock_session = MagicMock()
        mock_session.prompt_async = AsyncMock(side_effect=KeyboardInterrupt())
        mock_session_class.return_value = mock_session

        with patch("prompt_toolkit.output.create_output") as mock_create_output:
            mock_create_output.return_value = MagicMock()

            with pytest.raises(KeyboardInterrupt):
                await ui.ask_user("Enter something: ")


@pytest.mark.asyncio
async def test_stdui_ask_user_no_prompt_shows_waiting_banner(capsys):
    """When prompt is empty, a 'waiting for confirmation' line goes to stderr."""
    ui = StdUI(assistant_name="zrb")

    with patch("prompt_toolkit.PromptSession", create=True) as mock_session_class:
        mock_session = MagicMock()
        mock_session.prompt_async = AsyncMock(return_value="ok")
        mock_session_class.return_value = mock_session
        with patch("prompt_toolkit.output.create_output") as mock_create_output:
            mock_create_output.return_value = MagicMock()
            await ui.ask_user("")

    captured = capsys.readouterr()
    assert "waiting for confirmation" in captured.err
    assert "Zrb" in captured.err  # capitalized


def test_stdui_stream_to_parent_writes_like_append(capsys):
    """stream_to_parent is a thin wrapper around append_to_output."""
    ui = StdUI()
    ui.stream_to_parent("streamed", flush=True, kind="text")
    captured = capsys.readouterr()
    assert "streamed" in captured.err


# --- ask_user_choice ----------------------------------------------------


def _spec(options, multi=False, index=1, total=1):
    return {
        "question": "Pick?",
        "options": options,
        "multi_select": multi,
        "header": "Pick",
        "index": index,
        "total": total,
    }


def _patch_dialog(selection, multi=False):
    """Patch the relevant dialog factory to return a dialog yielding `selection`."""
    dialog = MagicMock()
    dialog.run_async = AsyncMock(return_value=selection)
    factory = MagicMock(return_value=dialog)
    target = (
        "prompt_toolkit.shortcuts.checkboxlist_dialog"
        if multi
        else "prompt_toolkit.shortcuts.radiolist_dialog"
    )
    return patch(target, factory), dialog


def test_option_text_with_and_without_description():
    assert _option_text({"label": "A", "description": "d"}) == "A — d"
    assert _option_text({"label": "B"}) == "B"


def test_resolve_choice_selection_single_and_multi():
    spec = _spec([{"label": "A"}, {"label": "B"}, {"label": "C"}])
    assert resolve_choice_selection(spec, 1) == "B"
    assert resolve_choice_selection(spec, [0, 2]) == "A, C"
    # Out-of-range indices are dropped.
    assert resolve_choice_selection(spec, [0, 99]) == "A"


@pytest.mark.asyncio
async def test_ask_user_choice_empty_options_returns_empty():
    ui = StdUI()
    assert await ui.ask_user_choice(_spec([])) == ""


@pytest.mark.asyncio
async def test_ask_user_choice_single_select_returns_label():
    ui = StdUI()
    dlg_patch, _ = _patch_dialog(selection=1)
    with dlg_patch, patch("prompt_toolkit.output.create_output", MagicMock()):
        result = await ui.ask_user_choice(_spec([{"label": "A"}, {"label": "B"}]))
    assert result == "B"


@pytest.mark.asyncio
async def test_ask_user_choice_multi_select_joins_labels():
    ui = StdUI()
    dlg_patch, _ = _patch_dialog(selection=[0, 2], multi=True)
    with dlg_patch, patch("prompt_toolkit.output.create_output", MagicMock()):
        result = await ui.ask_user_choice(
            _spec([{"label": "A"}, {"label": "B"}, {"label": "C"}], multi=True)
        )
    assert result == "A, C"


@pytest.mark.asyncio
async def test_ask_user_choice_cancel_raises_keyboard_interrupt():
    ui = StdUI()
    dlg_patch, _ = _patch_dialog(selection=None)
    with dlg_patch, patch("prompt_toolkit.output.create_output", MagicMock()):
        with pytest.raises(KeyboardInterrupt):
            await ui.ask_user_choice(_spec([{"label": "A"}]))


@pytest.mark.asyncio
async def test_ask_user_choice_nothing_selected_returns_no_answer():
    ui = StdUI()
    dlg_patch, _ = _patch_dialog(selection=[], multi=True)
    with dlg_patch, patch("prompt_toolkit.output.create_output", MagicMock()):
        result = await ui.ask_user_choice(_spec([{"label": "A"}], multi=True))
    assert result == "(no answer)"


@pytest.mark.asyncio
async def test_ask_user_choice_free_text_prompts_for_input():
    ui = StdUI()
    dlg_patch, _ = _patch_dialog(selection=_FREE_TEXT)
    mock_session = MagicMock()
    mock_session.prompt_async = AsyncMock(return_value="my own answer  ")
    with dlg_patch, patch("prompt_toolkit.output.create_output", MagicMock()), patch(
        "prompt_toolkit.PromptSession", create=True, return_value=mock_session
    ):
        result = await ui.ask_user_choice(_spec([{"label": "A"}]))
    assert result == "my own answer"


@pytest.mark.asyncio
async def test_ask_user_choice_multi_free_text_combines_checked_and_typed():
    """Multi-select + 'type my own' → checked options plus the typed answer."""
    ui = StdUI()
    dlg_patch, _ = _patch_dialog(selection=[0, 2, _FREE_TEXT], multi=True)
    mock_session = MagicMock()
    mock_session.prompt_async = AsyncMock(return_value="custom")
    with dlg_patch, patch("prompt_toolkit.output.create_output", MagicMock()), patch(
        "prompt_toolkit.PromptSession", create=True, return_value=mock_session
    ):
        result = await ui.ask_user_choice(
            _spec([{"label": "A"}, {"label": "B"}, {"label": "C"}], multi=True)
        )
    assert result == "A, C, custom"
