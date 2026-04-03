"""Tests for terminal.py - Terminal size utilities."""

import os
import sys
from unittest.mock import MagicMock, patch

import pytest


class TestTerminalSize:
    """Test TerminalSize NamedTuple."""

    def test_terminal_size_creation(self):
        """Test creating TerminalSize."""
        from zrb.util.cli.terminal import TerminalSize

        size = TerminalSize(columns=80, lines=24)
        assert size.columns == 80
        assert size.lines == 24

    def test_terminal_size_immutable(self):
        """Test TerminalSize is immutable."""
        from zrb.util.cli.terminal import TerminalSize

        size = TerminalSize(columns=80, lines=24)
        with pytest.raises(AttributeError):
            size.columns = 100

    def test_terminal_size_unpack(self):
        """Test TerminalSize can be unpacked."""
        from zrb.util.cli.terminal import TerminalSize

        size = TerminalSize(columns=100, lines=30)
        cols, lines = size
        assert cols == 100
        assert lines == 30


class TestGetTerminalSize:
    """Test get_terminal_size function."""

    def test_fallback_default(self):
        """Test get_terminal_size with default fallback."""
        from zrb.util.cli.terminal import get_terminal_size

        # When streams are None or unavailable, should return fallback
        with patch.object(sys, "__stdout__", None):
            with patch.object(sys, "__stderr__", None):
                with patch.object(sys, "__stdin__", None):
                    with patch("shutil.get_terminal_size") as mock_shutil:
                        mock_shutil.return_value.columns = 80
                        mock_shutil.return_value.lines = 24
                        size = get_terminal_size()
                        assert size.columns == 80
                        assert size.lines == 24

    def test_custom_fallback(self):
        """Test get_terminal_size with custom fallback."""
        from zrb.util.cli.terminal import get_terminal_size

        with patch.object(sys, "__stdout__", None):
            with patch.object(sys, "__stderr__", None):
                with patch.object(sys, "__stdin__", None):
                    with patch("shutil.get_terminal_size") as mock_shutil:
                        mock_shutil.return_value.columns = 120
                        mock_shutil.return_value.lines = 40
                        size = get_terminal_size(fallback=(120, 40))
                        assert size.columns == 120
                        assert size.lines == 40

    def test_returns_terminal_size(self):
        """Test that get_terminal_size returns TerminalSize."""
        from zrb.util.cli.terminal import TerminalSize, get_terminal_size

        # The function should return a TerminalSize
        size = get_terminal_size()
        assert isinstance(size, TerminalSize)

    def test_with_mocked_stdout(self):
        """Test get_terminal_size with mocked stdout."""
        from zrb.util.cli.terminal import get_terminal_size

        mock_stdout = MagicMock()
        mock_stdout.fileno.return_value = 1

        # Mock os.get_terminal_size to return values
        mock_size = MagicMock()
        mock_size.columns = 100
        mock_size.lines = 50

        with patch.object(sys, "__stdout__", mock_stdout):
            with patch("os.get_terminal_size", return_value=mock_size):
                size = get_terminal_size()
                assert size.columns == 100
                assert size.lines == 50

    def test_handles_os_error(self):
        """Test get_terminal_size handles OSError gracefully."""
        from zrb.util.cli.terminal import get_terminal_size

        mock_stdout = MagicMock()
        mock_stdout.fileno.return_value = 1

        with patch.object(sys, "__stdout__", mock_stdout):
            with patch.object(sys, "__stderr__", None):
                with patch.object(sys, "__stdin__", None):
                    with patch("os.get_terminal_size", side_effect=OSError("No tty")):
                        with patch("shutil.get_terminal_size") as mock_shutil:
                            mock_shutil.return_value.columns = 80
                            mock_shutil.return_value.lines = 24
                            size = get_terminal_size()
                            assert size.columns == 80

    def test_handles_value_error(self):
        """Test get_terminal_size handles ValueError gracefully."""
        from zrb.util.cli.terminal import get_terminal_size

        mock_stdout = MagicMock()
        mock_stdout.fileno.return_value = 1

        with patch.object(sys, "__stdout__", mock_stdout):
            with patch.object(sys, "__stderr__", None):
                with patch.object(sys, "__stdin__", None):
                    with patch(
                        "os.get_terminal_size", side_effect=ValueError("Bad fd")
                    ):
                        with patch("shutil.get_terminal_size") as mock_shutil:
                            mock_shutil.return_value.columns = 80
                            mock_shutil.return_value.lines = 24
                            size = get_terminal_size()
                            assert size.columns == 80

    def test_handles_attribute_error(self):
        """Test get_terminal_size handles AttributeError gracefully."""
        from zrb.util.cli.terminal import get_terminal_size

        mock_stdout = MagicMock()
        mock_stdout.fileno.side_effect = AttributeError("No fileno")

        with patch.object(sys, "__stdout__", mock_stdout):
            with patch.object(sys, "__stderr__", None):
                with patch.object(sys, "__stdin__", None):
                    with patch("shutil.get_terminal_size") as mock_shutil:
                        mock_shutil.return_value.columns = 80
                        mock_shutil.return_value.lines = 24
                        size = get_terminal_size()
                        assert size.columns == 80

    def test_shutil_exception_fallback(self):
        """Test get_terminal_size fallback when shutil raises exception."""
        from zrb.util.cli.terminal import get_terminal_size

        with patch.object(sys, "__stdout__", None):
            with patch.object(sys, "__stderr__", None):
                with patch.object(sys, "__stdin__", None):
                    with patch(
                        "shutil.get_terminal_size", side_effect=RuntimeError("Error")
                    ):
                        size = get_terminal_size(fallback=(100, 30))
                        assert size.columns == 100
                        assert size.lines == 30

    def test_stderr_stream_success(self):
        """Test get_terminal_size uses stderr when stdout fails."""
        from zrb.util.cli.terminal import get_terminal_size

        mock_stdout = MagicMock()
        mock_stdout.fileno.side_effect = OSError("No tty")

        mock_stderr = MagicMock()
        mock_stderr.fileno.return_value = 2

        mock_size = MagicMock()
        mock_size.columns = 90
        mock_size.lines = 40

        with patch.object(sys, "__stdout__", mock_stdout):
            with patch.object(sys, "__stderr__", mock_stderr):
                with patch.object(sys, "__stdin__", None):
                    with patch("os.get_terminal_size", return_value=mock_size):
                        size = get_terminal_size()
                        assert size.columns == 90
                        assert size.lines == 40

    def test_stdin_stream_success(self):
        """Test get_terminal_size uses stdin when stdout and stderr fail."""
        from zrb.util.cli.terminal import get_terminal_size

        mock_stdout = MagicMock()
        mock_stdout.fileno.side_effect = OSError("No tty")

        mock_stderr = MagicMock()
        mock_stderr.fileno.side_effect = OSError("No tty")

        mock_stdin = MagicMock()
        mock_stdin.fileno.return_value = 0

        mock_size = MagicMock()
        mock_size.columns = 85
        mock_size.lines = 35

        with patch.object(sys, "__stdout__", mock_stdout):
            with patch.object(sys, "__stderr__", mock_stderr):
                with patch.object(sys, "__stdin__", mock_stdin):
                    with patch("os.get_terminal_size", return_value=mock_size):
                        size = get_terminal_size()
                        assert size.columns == 85
                        assert size.lines == 35
