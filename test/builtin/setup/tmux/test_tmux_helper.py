"""Tests for tmux_helper.py - Tmux installation command generation."""

import os
from unittest.mock import MagicMock, patch

from zrb.builtin.setup.tmux.tmux_helper import (
    check_inexist_tpm_dir,
    get_install_tmux_cmd,
)


def test_check_inexist_tpm_dir_exists():
    """Test check_inexist_tpm_dir when ~/.tmux/plugins/tpm exists."""
    with patch.dict(os.environ, {"HOME": "/tmp"}):
        with patch("os.path.isdir", return_value=True):
            ctx = MagicMock()
            result = check_inexist_tpm_dir(ctx)
            assert result is False


def test_check_inexist_tpm_dir_not_exists():
    """Test check_inexist_tpm_dir when ~/.tmux/plugins/tpm does not exist."""
    with patch.dict(os.environ, {"HOME": "/tmp"}):
        with patch("os.path.isdir", return_value=False):
            ctx = MagicMock()
            result = check_inexist_tpm_dir(ctx)
            assert result is True


def test_get_install_tmux_cmd_with_apt():
    """Test tmux install command with apt package manager."""
    ctx = MagicMock()
    ctx.input = {"package-manager": "apt", "use-sudo": False}
    result = get_install_tmux_cmd(ctx)
    assert result == "apt install tmux"


def test_get_install_tmux_cmd_with_apt_sudo():
    """Test tmux install command with apt and sudo."""
    ctx = MagicMock()
    ctx.input = {"package-manager": "apt", "use-sudo": True}
    result = get_install_tmux_cmd(ctx)
    assert result == "sudo apt install tmux"


def test_get_install_tmux_cmd_with_pacman():
    """Test tmux install command with pacman package manager."""
    ctx = MagicMock()
    ctx.input = {"package-manager": "pacman", "use-sudo": False}
    result = get_install_tmux_cmd(ctx)
    assert result == "pacman -S tmux"


def test_get_install_tmux_cmd_with_pacman_sudo():
    """Test tmux install command with pacman and sudo."""
    ctx = MagicMock()
    ctx.input = {"package-manager": "pacman", "use-sudo": True}
    result = get_install_tmux_cmd(ctx)
    assert result == "sudo pacman -S tmux"


def test_get_install_tmux_cmd_with_dnf():
    """Test tmux install command with dnf package manager."""
    ctx = MagicMock()
    ctx.input = {"package-manager": "dnf", "use-sudo": False}
    result = get_install_tmux_cmd(ctx)
    assert result == "dnf install tmux"


def test_get_install_tmux_cmd_with_dnf_sudo():
    """Test tmux install command with dnf and sudo."""
    ctx = MagicMock()
    ctx.input = {"package-manager": "dnf", "use-sudo": True}
    result = get_install_tmux_cmd(ctx)
    assert result == "sudo dnf install tmux"


def test_get_install_tmux_cmd_with_brew():
    """Test tmux install command with brew package manager (no sudo)."""
    ctx = MagicMock()
    ctx.input = {"package-manager": "brew", "use-sudo": False}
    result = get_install_tmux_cmd(ctx)
    assert result == "brew install tmux"


def test_get_install_tmux_cmd_with_brew_sudo_ignored():
    """Test tmux install command with brew and sudo (brew typically doesn't use sudo)."""
    ctx = MagicMock()
    ctx.input = {"package-manager": "brew", "use-sudo": True}
    result = get_install_tmux_cmd(ctx)
    # Even with use-sudo=True, the function will add sudo prefix
    assert result == "sudo brew install tmux"
