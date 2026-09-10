"""Shell and platform detection: which shell `CFG.SHELL` resolves to on each
platform, the Windows POSIX-shell lookup behind it, and the Termux/WSL probes.

Split out of `test_config_foundation.py` (AGENTS.md -> Test Guidelines: split
by feature group past 500 lines); the rest of that file covers the config
object itself.
"""

from unittest import mock

from zrb.config.config import Config
from zrb.config.helper import (
    get_current_shell,
    get_windows_posix_shell,
    is_termux,
    is_wsl,
)


def test_default_shell_env_var_set(monkeypatch):
    monkeypatch.setenv("ZRB_SHELL", "my-shell")
    config = Config()
    assert config.SHELL == "my-shell"


def _which(*present):
    """A shutil.which stub that 'finds' only the named executables."""
    return lambda candidate: f"/usr/bin/{candidate}" if candidate in present else None


def _no_posix_shell():
    """Stand in for a Windows box with no POSIX shell installed.

    `get_windows_posix_shell` probes the filesystem for the standard Git
    install roots, so stubbing `shutil.which` alone does not isolate these --
    on any Windows machine that actually has Git, the real bash won. It is
    patched by name; the ordering it participates in is what these cover, and
    the lookup itself is covered further down.
    """
    return mock.patch("zrb.config.helper.get_windows_posix_shell", return_value="")


@mock.patch("platform.system", return_value="Windows")
def test_default_shell_windows(mock_platform_system, monkeypatch):
    monkeypatch.delenv("ZRB_SHELL", raising=False)
    config = Config()
    with (
        _no_posix_shell(),
        mock.patch("shutil.which", side_effect=_which("powershell")),
    ):
        assert config.SHELL == "powershell"
        assert get_current_shell() == "powershell"


@mock.patch("platform.system", return_value="Windows")
def test_default_shell_windows_prefers_pwsh(mock_platform_system, monkeypatch):
    monkeypatch.delenv("ZRB_SHELL", raising=False)
    with (
        _no_posix_shell(),
        mock.patch("shutil.which", side_effect=_which("pwsh", "powershell")),
    ):
        assert get_current_shell() == "pwsh"


@mock.patch("platform.system", return_value="Windows")
def test_default_shell_windows_prefers_bash_over_powershell(
    mock_platform_system, monkeypatch
):
    """Git Bash (ships on GitHub's windows-latest runner, and a common dev
    install) wins over PowerShell -- most zrb shell commands are POSIX syntax,
    so a POSIX shell is the better default.

    Its *absolute path* is what comes back, not the name: PATH's own first
    `bash` on Windows is `System32\\bash.exe`, the WSL launcher, so the name
    alone would not name this shell when it is handed to a subprocess.
    """
    monkeypatch.delenv("ZRB_SHELL", raising=False)
    git_bash = "C:\\Program Files\\Git\\bin\\bash.exe"
    with (
        mock.patch("zrb.config.helper.get_windows_posix_shell", return_value=git_bash),
        mock.patch("shutil.which", side_effect=_which("pwsh", "powershell")),
    ):
        assert get_current_shell() == git_bash


@mock.patch("platform.system", return_value="Windows")
def test_default_shell_windows_falls_back_to_cmd(mock_platform_system, monkeypatch):
    monkeypatch.delenv("ZRB_SHELL", raising=False)
    # Neither pwsh nor powershell present -> cmd, which always exists on Windows.
    with _no_posix_shell(), mock.patch("shutil.which", side_effect=_which()):
        assert get_current_shell() == "cmd"


@mock.patch("platform.system", return_value="Windows")
def test_windows_posix_shell_found_next_to_git(mock_platform_system):
    """Git's own prefix is the first place to look -- it finds an install
    wherever the user put it, not just under Program Files."""
    git_bash = "C:\\tools\\Git\\bin\\bash.exe"
    with (
        mock.patch(
            "shutil.which", side_effect=lambda c: "C:\\tools\\Git\\cmd\\git.exe"
        ),
        mock.patch("os.path.isfile", side_effect=lambda p: p == git_bash),
    ):
        assert get_windows_posix_shell() == git_bash


@mock.patch("platform.system", return_value="Windows")
def test_windows_posix_shell_rejects_the_wsl_launcher(mock_platform_system):
    """`System32\\bash.exe` is the WSL launcher, not a shell: with no distro
    installed every command through it fails while still printing output. A
    PATH hit there is no hit at all."""
    with (
        mock.patch("os.path.isfile", return_value=False),
        mock.patch(
            "shutil.which",
            side_effect=lambda c: (
                "C:\\Windows\\System32\\bash.exe" if c == "bash" else None
            ),
        ),
    ):
        assert get_windows_posix_shell() == ""


@mock.patch("platform.system", return_value="Windows")
def test_windows_posix_shell_accepts_a_bash_outside_the_windows_dir(
    mock_platform_system,
):
    """A bash anywhere else on PATH is a real one -- an MSYS2 or Cygwin
    install, say -- and is used as it is found."""
    msys_bash = "C:\\msys64\\usr\\bin\\bash.exe"
    with (
        mock.patch("os.path.isfile", return_value=False),
        mock.patch(
            "shutil.which", side_effect=lambda c: msys_bash if c == "bash" else None
        ),
    ):
        assert get_windows_posix_shell() == msys_bash


def test_windows_posix_shell_is_empty_off_windows():
    """Nothing to disambiguate anywhere else: `bash` means bash."""
    assert get_windows_posix_shell() == ""


@mock.patch("platform.system", return_value="Linux")
def test_default_shell_zsh(mock_platform_system, monkeypatch):
    monkeypatch.delenv("ZRB_SHELL", raising=False)
    monkeypatch.setenv("SHELL", "/bin/zsh")
    config = Config()
    with mock.patch("shutil.which", side_effect=_which("zsh", "bash", "sh")):
        assert config.SHELL == "zsh"
        assert get_current_shell() == "zsh"


@mock.patch("platform.system", return_value="Linux")
def test_default_shell_bash(mock_platform_system, monkeypatch):
    monkeypatch.delenv("ZRB_SHELL", raising=False)
    monkeypatch.setenv("SHELL", "/bin/bash")
    config = Config()
    with mock.patch("shutil.which", side_effect=_which("bash", "sh")):
        assert config.SHELL == "bash"
        assert get_current_shell() == "bash"


@mock.patch("platform.system", return_value="Linux")
def test_default_shell_alpine_falls_back_to_sh(mock_platform_system, monkeypatch):
    # Alpine: $SHELL unset and bash not installed -> must resolve to sh, not bash.
    monkeypatch.delenv("ZRB_SHELL", raising=False)
    monkeypatch.setenv("SHELL", "")
    with mock.patch("shutil.which", side_effect=_which("sh")):
        assert get_current_shell() == "sh"


@mock.patch("platform.system", return_value="Linux")
def test_default_shell_zsh_requested_but_absent(mock_platform_system, monkeypatch):
    # $SHELL says zsh but it isn't installed -> fall back to an existing shell.
    monkeypatch.delenv("ZRB_SHELL", raising=False)
    monkeypatch.setenv("SHELL", "/bin/zsh")
    with mock.patch("shutil.which", side_effect=_which("bash", "sh")):
        assert get_current_shell() == "bash"


def test_is_termux_detects_termux_version(monkeypatch):
    monkeypatch.setenv("TERMUX_VERSION", "0.118.0")
    monkeypatch.delenv("PREFIX", raising=False)
    assert is_termux() is True


def test_is_termux_detects_com_termux_prefix(monkeypatch):
    monkeypatch.delenv("TERMUX_VERSION", raising=False)
    monkeypatch.setenv("PREFIX", "/data/data/com.termux/files/usr")
    assert is_termux() is True


def test_is_termux_false_off_termux(monkeypatch):
    monkeypatch.delenv("TERMUX_VERSION", raising=False)
    monkeypatch.setenv("PREFIX", "/usr/local")
    monkeypatch.delenv("ANDROID_ROOT", raising=False)
    assert is_termux() is False


def test_is_termux_detects_android_root(monkeypatch):
    monkeypatch.delenv("TERMUX_VERSION", raising=False)
    monkeypatch.delenv("PREFIX", raising=False)
    monkeypatch.setenv("ANDROID_ROOT", "/system")
    assert is_termux() is True


def test_is_wsl_detects_distro_name(monkeypatch):
    monkeypatch.setenv("WSL_DISTRO_NAME", "Ubuntu")
    monkeypatch.delenv("WSLENV", raising=False)
    assert is_wsl() is True


def test_is_wsl_detects_wslenv(monkeypatch):
    monkeypatch.delenv("WSL_DISTRO_NAME", raising=False)
    monkeypatch.setenv("WSLENV", "TERM/u")
    assert is_wsl() is True


def test_is_wsl_false_off_wsl(monkeypatch):
    monkeypatch.delenv("WSL_DISTRO_NAME", raising=False)
    monkeypatch.delenv("WSLENV", raising=False)
    assert is_wsl() is False


def test_cfg_is_termux_auto_detected(monkeypatch):
    monkeypatch.delenv("ZRB_IS_TERMUX", raising=False)
    monkeypatch.setenv("TERMUX_VERSION", "0.118.0")
    assert Config().IS_TERMUX is True


def test_cfg_is_termux_env_override_wins(monkeypatch):
    # Auto-detection says Termux, but an explicit override forces it off.
    monkeypatch.setenv("TERMUX_VERSION", "0.118.0")
    monkeypatch.setenv("ZRB_IS_TERMUX", "false")
    assert Config().IS_TERMUX is False
