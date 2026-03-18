"""Tests for env.py - Environment variable handling."""

import os
from unittest.mock import MagicMock, patch

import pytest


class TestEnv:
    """Test Env class."""

    def test_init_with_defaults(self):
        """Test Env initialization with default parameters."""
        from zrb.env.env import Env

        env = Env(name="TEST_VAR", default="default_value")

        assert env._name == "TEST_VAR"
        assert env._default == "default_value"
        assert env._auto_render is True
        assert env._link_to_os is True
        assert env._os_name is None

    def test_init_with_custom_params(self):
        """Test Env initialization with custom parameters."""
        from zrb.env.env import Env

        env = Env(
            name="TEST_VAR",
            default="default_value",
            auto_render=False,
            link_to_os=False,
            os_name="CUSTOM_OS_NAME",
        )

        assert env._name == "TEST_VAR"
        assert env._default == "default_value"
        assert env._auto_render is False
        assert env._link_to_os is False
        assert env._os_name == "CUSTOM_OS_NAME"

    def test_update_context_with_os_env(self):
        """Test update_context reads from os.environ."""
        from zrb.env.env import Env

        env = Env(name="TEST_VAR", default="default_value")

        mock_ctx = MagicMock()
        mock_ctx.env = {}

        with patch.dict(os.environ, {"TEST_VAR": "from_os"}):
            env.update_context(mock_ctx)

        assert mock_ctx.env["TEST_VAR"] == "from_os"

    def test_update_context_with_os_name(self):
        """Test update_context uses custom os_name."""
        from zrb.env.env import Env

        env = Env(name="TEST_VAR", default="default_value", os_name="CUSTOM_OS_VAR")

        mock_ctx = MagicMock()
        mock_ctx.env = {}

        with patch.dict(os.environ, {"CUSTOM_OS_VAR": "custom_value"}):
            env.update_context(mock_ctx)

        assert mock_ctx.env["TEST_VAR"] == "custom_value"

    def test_update_context_without_link_to_os(self):
        """Test update_context without link_to_os uses default."""
        from zrb.env.env import Env

        env = Env(name="TEST_VAR", default="default_value", link_to_os=False)

        mock_ctx = MagicMock()
        mock_ctx.env = {}

        with patch("zrb.env.env.get_str_attr") as mock_get_str_attr:
            mock_get_str_attr.return_value = "default_value"
            env.update_context(mock_ctx)

        assert mock_ctx.env["TEST_VAR"] == "default_value"

    def test_update_context_os_env_missing_uses_default(self):
        """Test update_context falls back to default when os env is missing."""
        from zrb.env.env import Env

        env = Env(name="NONEXISTENT_VAR_XYZ", default="fallback_value")

        mock_ctx = MagicMock()
        mock_ctx.env = {}

        # Make sure the env var doesn't exist
        if "NONEXISTENT_VAR_XYZ" in os.environ:
            del os.environ["NONEXISTENT_VAR_XYZ"]

        with patch("zrb.env.env.get_str_attr") as mock_get_str_attr:
            mock_get_str_attr.return_value = "fallback_value"
            env.update_context(mock_ctx)

        assert mock_ctx.env["NONEXISTENT_VAR_XYZ"] == "fallback_value"

    def test_update_context_multiple_times(self):
        """Test update_context called multiple times."""
        from zrb.env.env import Env

        env = Env(name="MULTI_VAR", default="default")

        mock_ctx = MagicMock()
        mock_ctx.env = {}

        with patch.dict(os.environ, {"MULTI_VAR": "os_value"}):
            env.update_context(mock_ctx)
            assert mock_ctx.env["MULTI_VAR"] == "os_value"

            # Second call should update again
            mock_ctx.env = {}
            env.update_context(mock_ctx)
            assert mock_ctx.env["MULTI_VAR"] == "os_value"


class TestEnvGetDefaultValue:
    """Test _get_default_value method."""

    def test_get_default_value_simple_string(self):
        """Test _get_default_value with simple string."""
        from zrb.env.env import Env

        env = Env(name="TEST", default="simple_default")
        mock_ctx = MagicMock()

        with patch("zrb.env.env.get_str_attr") as mock_get_str_attr:
            mock_get_str_attr.return_value = "simple_default"
            result = env._get_default_value(mock_ctx)

        assert result == "simple_default"

    def test_get_default_value_with_auto_render_false(self):
        """Test _get_default_value with auto_render=False."""
        from zrb.env.env import Env

        env = Env(name="TEST", default="${VAR}", auto_render=False)
        mock_ctx = MagicMock()

        with patch("zrb.env.env.get_str_attr") as mock_get_str_attr:
            mock_get_str_attr.return_value = "${VAR}"
            result = env._get_default_value(mock_ctx)

        assert result == "${VAR}"


class TestEnvIntegration:
    """Integration tests for Env class."""

    def test_env_with_callable_default(self):
        """Test Env with callable default."""
        from zrb.env.env import Env

        def get_default(ctx):
            return "dynamic_default"

        env = Env(name="DYNAMIC_VAR", default=get_default, link_to_os=False)
        mock_ctx = MagicMock()
        mock_ctx.env = {}

        with patch("zrb.env.env.get_str_attr") as mock_get_str_attr:
            mock_get_str_attr.return_value = "dynamic_default"
            env.update_context(mock_ctx)

        assert mock_ctx.env["DYNAMIC_VAR"] == "dynamic_default"
