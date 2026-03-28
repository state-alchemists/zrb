"""Tests for StdUI class."""

import asyncio
import sys
from io import StringIO
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from zrb.llm.ui.std_ui import StdUI


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
