"""Tests for zsh_helper.py - Zsh installation command generation."""

from unittest.mock import MagicMock

from zrb.builtin.setup.zsh.zsh_helper import get_install_zsh_cmd


def test_get_install_zsh_cmd_with_apt():
    """Test zsh install command with apt package manager."""
    ctx = MagicMock()
    ctx.input = {"package-manager": "apt", "use-sudo": False}
    result = get_install_zsh_cmd(ctx)
    assert result == "apt install zsh"


def test_get_install_zsh_cmd_with_apt_sudo():
    """Test zsh install command with apt and sudo."""
    ctx = MagicMock()
    ctx.input = {"package-manager": "apt", "use-sudo": True}
    result = get_install_zsh_cmd(ctx)
    assert result == "sudo apt install zsh"


def test_get_install_zsh_cmd_with_pacman():
    """Test zsh install command with pacman package manager."""
    ctx = MagicMock()
    ctx.input = {"package-manager": "pacman", "use-sudo": False}
    result = get_install_zsh_cmd(ctx)
    assert result == "pacman -S zsh"


def test_get_install_zsh_cmd_with_pacman_sudo():
    """Test zsh install command with pacman and sudo."""
    ctx = MagicMock()
    ctx.input = {"package-manager": "pacman", "use-sudo": True}
    result = get_install_zsh_cmd(ctx)
    assert result == "sudo pacman -S zsh"


def test_get_install_zsh_cmd_with_dnf():
    """Test zsh install command with dnf package manager."""
    ctx = MagicMock()
    ctx.input = {"package-manager": "dnf", "use-sudo": False}
    result = get_install_zsh_cmd(ctx)
    assert result == "dnf install zsh"


def test_get_install_zsh_cmd_with_dnf_sudo():
    """Test zsh install command with dnf and sudo."""
    ctx = MagicMock()
    ctx.input = {"package-manager": "dnf", "use-sudo": True}
    result = get_install_zsh_cmd(ctx)
    assert result == "sudo dnf install zsh"


def test_get_install_zsh_cmd_with_brew():
    """Test zsh install command with brew package manager."""
    ctx = MagicMock()
    ctx.input = {"package-manager": "brew", "use-sudo": False}
    result = get_install_zsh_cmd(ctx)
    assert result == "brew install zsh"
