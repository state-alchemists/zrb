"""Tests for common_input.py - OS-aware defaults for setup task inputs."""

from unittest.mock import MagicMock, patch

from zrb.builtin.setup.common_input import (
    get_default_package_manager,
    get_default_use_sudo,
)


def test_get_default_package_manager_on_macos():
    """macOS has no apt/dnf/pacman/zypper/pkg, so brew should be the default."""
    with patch("zrb.builtin.setup.common_input.sys.platform", "darwin"):
        assert get_default_package_manager(MagicMock()) == "brew"


def test_get_default_package_manager_on_linux():
    """Linux defaults to apt."""
    with patch("zrb.builtin.setup.common_input.sys.platform", "linux"):
        assert get_default_package_manager(MagicMock()) == "apt"


def test_get_default_use_sudo_on_macos():
    """brew must run unprivileged, so sudo should default to off on macOS."""
    with patch("zrb.builtin.setup.common_input.sys.platform", "darwin"):
        assert get_default_use_sudo(MagicMock()) is False


def test_get_default_use_sudo_on_linux():
    """apt/dnf/pacman/etc. need sudo by default on Linux."""
    with patch("zrb.builtin.setup.common_input.sys.platform", "linux"):
        assert get_default_use_sudo(MagicMock()) is True
