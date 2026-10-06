"""Tests for asdf setup helpers."""

import os
import tempfile
from unittest.mock import MagicMock, patch

from zrb.builtin.setup.asdf.asdf_helper import (
    check_inexist_asdf_dir,
    get_install_prerequisites_cmd,
    setup_asdf_ps_config,
    setup_asdf_sh_config,
)


def test_get_install_prerequisites_cmd_with_apt():
    """Build the apt prerequisites command."""
    ctx = MagicMock()
    ctx.input = {"package-manager": "apt", "use-sudo": False}
    result = get_install_prerequisites_cmd(ctx)
    assert result == "apt install curl git"


def test_get_install_prerequisites_cmd_with_apt_sudo():
    """Build the sudo apt prerequisites command."""
    ctx = MagicMock()
    ctx.input = {"package-manager": "apt", "use-sudo": True}
    result = get_install_prerequisites_cmd(ctx)
    assert result == "sudo apt install curl git"


def test_get_install_prerequisites_cmd_with_pacman():
    """Build the pacman prerequisites command."""
    ctx = MagicMock()
    ctx.input = {"package-manager": "pacman", "use-sudo": False}
    result = get_install_prerequisites_cmd(ctx)
    assert result == "pacman -S curl git"


def test_get_install_prerequisites_cmd_with_pacman_sudo():
    """Build the sudo pacman prerequisites command."""
    ctx = MagicMock()
    ctx.input = {"package-manager": "pacman", "use-sudo": True}
    result = get_install_prerequisites_cmd(ctx)
    assert result == "sudo pacman -S curl git"


def test_get_install_prerequisites_cmd_with_brew():
    """Build the brew prerequisites command."""
    ctx = MagicMock()
    ctx.input = {"package-manager": "brew", "use-sudo": False}
    result = get_install_prerequisites_cmd(ctx)
    assert result == "brew install coreutils curl git"


def test_get_install_prerequisites_cmd_with_spack():
    """Build the spack prerequisites command."""
    ctx = MagicMock()
    ctx.input = {"package-manager": "spack", "use-sudo": False}
    result = get_install_prerequisites_cmd(ctx)
    assert result == "spack install coreutils curl git"


def test_get_install_prerequisites_cmd_with_dnf():
    """Build the dnf prerequisites command."""
    ctx = MagicMock()
    ctx.input = {"package-manager": "dnf", "use-sudo": False}
    result = get_install_prerequisites_cmd(ctx)
    assert result == "dnf install curl git"


def test_check_inexist_asdf_dir_exists():
    """Return false when the asdf directory exists."""
    with patch.dict(os.environ, {"HOME": "/tmp"}):
        with patch("os.path.isdir", return_value=True):
            ctx = MagicMock()
            result = check_inexist_asdf_dir(ctx)
            assert result is False


def test_check_inexist_asdf_dir_not_exists():
    """Return true when the asdf directory is absent."""
    with patch.dict(os.environ, {"HOME": "/tmp"}):
        with patch("os.path.isdir", return_value=False):
            ctx = MagicMock()
            result = check_inexist_asdf_dir(ctx)
            assert result is True


def test_setup_asdf_sh_config_creates_file():
    """Create the shell config file when absent."""
    with tempfile.TemporaryDirectory() as tmpdir:
        file_path = os.path.join(tmpdir, ".bashrc")
        setup_asdf_sh_config(file_path)
        assert os.path.isfile(file_path)


def test_setup_asdf_sh_config_adds_config():
    """Add the asdf shell config block."""
    with tempfile.TemporaryDirectory() as tmpdir:
        file_path = os.path.join(tmpdir, ".bashrc")
        setup_asdf_sh_config(file_path)
        with open(file_path, "r") as f:
            content = f.read()
        assert '. "$HOME/.asdf/asdf.sh"' in content


def test_setup_asdf_sh_config_does_not_duplicate():
    """Test setup_asdf_sh_config does not add duplicate config."""
    with tempfile.TemporaryDirectory() as tmpdir:
        file_path = os.path.join(tmpdir, ".bashrc")
        setup_asdf_sh_config(file_path)
        setup_asdf_sh_config(file_path)  # Call twice
        with open(file_path, "r") as f:
            content = f.read()
        # Should only appear once
        assert content.count('. "$HOME/.asdf/asdf.sh"') == 1


def test_setup_asdf_sh_config_preserves_existing_content():
    """Test setup_asdf_sh_config preserves existing file content."""
    with tempfile.TemporaryDirectory() as tmpdir:
        file_path = os.path.join(tmpdir, ".bashrc")
        # Create file with existing content
        with open(file_path, "w") as f:
            f.write("export PATH=$PATH:/usr/local/bin\n")
        setup_asdf_sh_config(file_path)
        with open(file_path, "r") as f:
            content = f.read()
        assert "export PATH=$PATH:/usr/local/bin" in content
        assert '. "$HOME/.asdf/asdf.sh"' in content


def test_setup_asdf_ps_config_adds_config():
    """Test setup_asdf_ps_config adds PowerShell config to file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        file_path = os.path.join(tmpdir, "profile.ps1")
        setup_asdf_ps_config(file_path)
        with open(file_path, "r") as f:
            content = f.read()
        assert '. "$HOME/.asdf/asdf.ps1"' in content


def test_setup_asdf_ps_config_does_not_duplicate():
    """Test setup_asdf_ps_config does not add duplicate config."""
    with tempfile.TemporaryDirectory() as tmpdir:
        file_path = os.path.join(tmpdir, "profile.ps1")
        setup_asdf_ps_config(file_path)
        setup_asdf_ps_config(file_path)  # Call twice
        with open(file_path, "r") as f:
            content = f.read()
        # Should only appear once
        assert content.count('. "$HOME/.asdf/asdf.ps1"') == 1
