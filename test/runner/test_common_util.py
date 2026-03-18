"""Tests for common_util.py - Command line utility functions."""

from unittest.mock import MagicMock, patch

import pytest


class TestGetTaskStrKwargs:
    """Test get_task_str_kwargs function."""

    def test_with_str_kwargs(self):
        """Test get_task_str_kwargs with provided str_kwargs."""
        from zrb.runner.common_util import get_task_str_kwargs

        mock_task = MagicMock()
        mock_input = MagicMock()
        mock_input.name = "input1"
        mock_input.allow_positional_parsing = True
        mock_input.always_prompt = False
        mock_input.update_shared_context = MagicMock()
        mock_task.inputs = [mock_input]

        mock_shared_ctx = MagicMock()

        with patch("zrb.runner.common_util.SharedContext") as mock_shared_ctx_cls:
            mock_shared_ctx_cls.return_value = mock_shared_ctx

            result = get_task_str_kwargs(
                task=mock_task,
                str_args=[],
                str_kwargs={"input1": "value1"},
                cli_mode=False,
            )

        assert result["input1"] == "value1"

    def test_with_str_args(self):
        """Test get_task_str_kwargs with positional str_args."""
        from zrb.runner.common_util import get_task_str_kwargs

        mock_task = MagicMock()
        mock_input = MagicMock()
        mock_input.name = "input1"
        mock_input.allow_positional_parsing = True
        mock_input.always_prompt = False
        mock_input.update_shared_context = MagicMock()
        mock_task.inputs = [mock_input]

        mock_shared_ctx = MagicMock()

        with patch("zrb.runner.common_util.SharedContext") as mock_shared_ctx_cls:
            mock_shared_ctx_cls.return_value = mock_shared_ctx

            result = get_task_str_kwargs(
                task=mock_task,
                str_args=["positional_value"],
                str_kwargs={},
                cli_mode=False,
            )

        assert result["input1"] == "positional_value"

    def test_with_default_value(self):
        """Test get_task_str_kwargs using default value."""
        from zrb.runner.common_util import get_task_str_kwargs

        mock_task = MagicMock()
        mock_input = MagicMock()
        mock_input.name = "input1"
        mock_input.allow_positional_parsing = True
        mock_input.always_prompt = False
        mock_input.get_default_str = MagicMock(return_value="default_value")
        mock_input.update_shared_context = MagicMock()
        mock_task.inputs = [mock_input]

        mock_shared_ctx = MagicMock()

        with patch("zrb.runner.common_util.SharedContext") as mock_shared_ctx_cls:
            mock_shared_ctx_cls.return_value = mock_shared_ctx

            result = get_task_str_kwargs(
                task=mock_task,
                str_args=[],
                str_kwargs={},
                cli_mode=False,
            )

        assert result["input1"] == "default_value"

    def test_with_cli_mode_and_always_prompt(self):
        """Test get_task_str_kwargs in CLI mode with always_prompt."""
        from zrb.runner.common_util import get_task_str_kwargs

        mock_task = MagicMock()
        mock_input = MagicMock()
        mock_input.name = "input1"
        mock_input.allow_positional_parsing = True
        mock_input.always_prompt = True
        mock_input.prompt_cli_str = MagicMock(return_value="prompted_value")
        mock_input.update_shared_context = MagicMock()
        mock_task.inputs = [mock_input]

        mock_shared_ctx = MagicMock()

        with patch("zrb.runner.common_util.SharedContext") as mock_shared_ctx_cls:
            mock_shared_ctx_cls.return_value = mock_shared_ctx

            result = get_task_str_kwargs(
                task=mock_task,
                str_args=[],
                str_kwargs={},
                cli_mode=True,  # CLI mode enabled
            )

        assert result["input1"] == "prompted_value"
        mock_input.prompt_cli_str.assert_called_once()

    def test_without_positional_parsing(self):
        """Test get_task_str_kwargs with input that doesn't allow positional parsing."""
        from zrb.runner.common_util import get_task_str_kwargs

        mock_task = MagicMock()
        mock_input = MagicMock()
        mock_input.name = "input1"
        mock_input.allow_positional_parsing = False  # Doesn't allow positional
        mock_input.always_prompt = False
        mock_input.get_default_str = MagicMock(return_value="default_value")
        mock_input.update_shared_context = MagicMock()
        mock_task.inputs = [mock_input]

        mock_shared_ctx = MagicMock()

        with patch("zrb.runner.common_util.SharedContext") as mock_shared_ctx_cls:
            mock_shared_ctx_cls.return_value = mock_shared_ctx

            result = get_task_str_kwargs(
                task=mock_task,
                str_args=["positional_value"],  # Should be ignored
                str_kwargs={},
                cli_mode=False,
            )

        # Should use default value, not positional
        assert result["input1"] == "default_value"

    def test_with_multiple_inputs(self):
        """Test get_task_str_kwargs with multiple inputs."""
        from zrb.runner.common_util import get_task_str_kwargs

        mock_input1 = MagicMock()
        mock_input1.name = "input1"
        mock_input1.allow_positional_parsing = True
        mock_input1.always_prompt = False
        mock_input1.update_shared_context = MagicMock()

        mock_input2 = MagicMock()
        mock_input2.name = "input2"
        mock_input2.allow_positional_parsing = True
        mock_input2.always_prompt = False
        mock_input2.get_default_str = MagicMock(return_value="default2")
        mock_input2.update_shared_context = MagicMock()

        mock_task = MagicMock()
        mock_task.inputs = [mock_input1, mock_input2]

        mock_shared_ctx = MagicMock()

        with patch("zrb.runner.common_util.SharedContext") as mock_shared_ctx_cls:
            mock_shared_ctx_cls.return_value = mock_shared_ctx

            result = get_task_str_kwargs(
                task=mock_task,
                str_args=["value1"],  # First positional for input1
                str_kwargs={"input2": "kwarg_value"},  # Kwarg for input2
                cli_mode=False,
            )

        assert result["input1"] == "value1"
        assert result["input2"] == "kwarg_value"

    def test_kwargs_override_positional(self):
        """Test that kwargs take precedence over positional args."""
        from zrb.runner.common_util import get_task_str_kwargs

        mock_input = MagicMock()
        mock_input.name = "input1"
        mock_input.allow_positional_parsing = True
        mock_input.always_prompt = False
        mock_input.update_shared_context = MagicMock()

        mock_task = MagicMock()
        mock_task.inputs = [mock_input]

        mock_shared_ctx = MagicMock()

        with patch("zrb.runner.common_util.SharedContext") as mock_shared_ctx_cls:
            mock_shared_ctx_cls.return_value = mock_shared_ctx

            result = get_task_str_kwargs(
                task=mock_task,
                str_args=["positional_value"],
                str_kwargs={"input1": "kwarg_value"},  # Overrides positional
                cli_mode=False,
            )

        assert result["input1"] == "kwarg_value"

    def test_empty_inputs_returns_empty_dict(self):
        """Test get_task_str_kwargs with no inputs."""
        from zrb.runner.common_util import get_task_str_kwargs

        mock_task = MagicMock()
        mock_task.inputs = []

        mock_shared_ctx = MagicMock()

        with patch("zrb.runner.common_util.SharedContext") as mock_shared_ctx_cls:
            mock_shared_ctx_cls.return_value = mock_shared_ctx

            result = get_task_str_kwargs(
                task=mock_task,
                str_args=["ignored"],
                str_kwargs={"ignored": "value"},
                cli_mode=False,
            )

        assert result == {}
