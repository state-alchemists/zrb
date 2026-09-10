import logging
import ntpath
import os
import platform
import re
import shutil
from functools import lru_cache


def get_env(env_name: str | list[str], default: str = "", prefix: str = "ZRB") -> str:
    env_name_list = env_name if isinstance(env_name, list) else [env_name]
    for name in env_name_list:
        value = os.getenv(f"{prefix}_{name}", None)
        if value is not None:
            return value
    return default


@lru_cache(maxsize=1)
def get_windows_posix_shell() -> str:
    """Absolute path to a real POSIX shell on Windows, or `""` when there is none.

    Cached because it is on a hot path and its answer cannot change within a
    run: `EnvField` re-evaluates `default_factory` on *every* `CFG.SHELL`
    read, and `resolve_shell` calls this again for a bare `bash`/`sh`, so an
    uncached lookup means a `shutil.which` PATH scan plus four `isfile` probes
    per command executed. Tests that stub `shutil.which`/`os.path.isfile` must
    call `get_windows_posix_shell.cache_clear()` first -- `conftest` does this
    automatically.

    A bare `shutil.which("bash")` is not enough, which is what made this a
    function. Windows ships `System32\\bash.exe` -- the WSL *launcher* -- and it
    wins the PATH lookup on a stock install. It is not a shell: with no distro
    installed it prints "Windows Subsystem for Linux has no installed
    distributions" as UTF-16 on stdout and exits 1, so every command run
    through it fails while looking like it produced output; and with a distro
    installed it runs inside the WSL filesystem namespace, where the caller's
    `D:\\...` working directory does not exist.

    Git for Windows ships a genuine bash, so it is what "bash" should mean
    here. It is located from `git` on PATH first (whatever prefix the user
    installed into), then the standard install roots, and only then from PATH
    -- and a PATH hit inside the Windows directory is rejected as the launcher
    again. Returns "" on non-Windows platforms, which have no such ambiguity.
    """
    if platform.system() != "Windows":
        return ""
    # `ntpath`, not `os.path`: these are Windows paths, and on Windows the two
    # are the same module anyway -- so building them this way costs nothing
    # there and keeps the whole lookup testable from any platform.
    candidates = []
    git_path = shutil.which("git")
    if git_path:
        # <root>/cmd/git.exe or <root>/bin/git.exe -> <root>/bin/bash.exe
        git_root = ntpath.dirname(ntpath.dirname(git_path))
        candidates.append(ntpath.join(git_root, "bin", "bash.exe"))
    local_programs = os.getenv("LOCALAPPDATA", "")
    for base in (
        os.getenv("ProgramFiles", ""),
        os.getenv("ProgramW6432", ""),
        os.getenv("ProgramFiles(x86)", ""),
        ntpath.join(local_programs, "Programs") if local_programs else "",
    ):
        if base:
            candidates.append(ntpath.join(base, "Git", "bin", "bash.exe"))
    for candidate in candidates:
        if os.path.isfile(candidate):
            return candidate
    for name in ("bash", "sh"):
        found = shutil.which(name)
        if found and not _is_in_windows_dir(found):
            return found
    return ""


def _is_in_windows_dir(path: str) -> bool:
    """Whether *path* sits under the Windows directory -- where the only `bash`
    is the WSL launcher.

    Compared through `ntpath` rather than `os.path`: the paths are Windows
    paths whichever platform is asking, and `ntpath.normcase` folds case and
    slashes without consulting the running OS -- so this stays a pure string
    question and the tests do not need a Windows host to ask it.
    """
    system_root = os.getenv("SystemRoot") or "C:\\Windows"
    prefix = ntpath.normcase(system_root).rstrip("\\") + "\\"
    return ntpath.normcase(path).startswith(prefix)


_EXE_SUFFIX = re.compile(r"\.exe$", re.IGNORECASE)


def get_shell_name(shell: str) -> str:
    """The bare shell name behind a shell setting: `bash` for `bash`,
    `/bin/bash` and `C:\\Program Files\\Git\\bin\\bash.exe` alike.

    Every name comparison against a shell setting has to go through here,
    because a Windows setting is an absolute `.exe` path (see
    `get_windows_posix_shell`, which `get_current_shell` returns directly):
    `shell.endswith("bash")` answers False for `...\\bin\\bash.exe`, which is
    the shell most likely to be configured on that platform. Both separators
    are split on rather than using `os.path`, so the answer does not depend on
    which platform is asking.
    """
    return _EXE_SUFFIX.sub("", re.split(r"[\\/]", shell)[-1]).lower()


def get_current_shell() -> str:
    """Return the name of a shell that actually exists on this system.

    Every returned name is verified with ``shutil.which`` so callers never get a
    shell that isn't installed (e.g. ``bash`` on a minimal Alpine image, or
    PowerShell on a stripped-down Windows). Final fallbacks (``sh`` / ``cmd``)
    are effectively always present on their respective platforms.
    """
    if platform.system() == "Windows":
        # Git Bash ships on GitHub's windows-latest runner (and is a common
        # dev install), and most of zrb's own shell commands are written in
        # POSIX syntax -- so a real POSIX shell is preferred over
        # PowerShell/cmd, matching the POSIX branch below rather than assuming
        # Windows means no POSIX shell is available.
        posix_shell = get_windows_posix_shell()
        if posix_shell:
            return posix_shell
        for candidate in ("pwsh", "powershell"):
            if shutil.which(candidate):
                return candidate
        return "cmd"
    current_shell = os.getenv("SHELL", "")
    if get_shell_name(current_shell) == "zsh" and shutil.which("zsh"):
        return "zsh"
    for candidate in ("bash", "sh"):
        if shutil.which(candidate):
            return candidate
    return "sh"


def is_termux() -> bool:
    """Best-effort detection of a Termux (Android) terminal.

    Termux exports ``TERMUX_VERSION`` and installs everything under a
    ``com.termux`` prefix. Either signal is enough; both are checked so the
    detection survives a stripped environment that drops ``TERMUX_VERSION``.
    As a fallback, ``ANDROID_ROOT`` (set to ``/system`` on every Android
    device) catches proot-based distros that lose ``TERMUX_VERSION`` and
    ``PREFIX``.
    Used to special-case keybindings: on Termux, Tab and Shift+Tab both emit
    byte ``0x09``, so the terminal cannot tell them apart.
    """
    if os.getenv("TERMUX_VERSION"):
        return True
    if "com.termux" in os.getenv("PREFIX", ""):
        return True
    if os.getenv("ANDROID_ROOT") == "/system":
        return True
    return False


def is_wsl() -> bool:
    """Best-effort detection of Windows Subsystem for Linux.

    WSL exports ``WSL_DISTRO_NAME`` (the distro name) on WSL2, and ``WSLENV``
    (the cross-boundary env-var passlist) on both WSL1 and WSL2. Either
    signal is enough.
    """
    return bool(os.environ.get("WSL_DISTRO_NAME") or os.environ.get("WSLENV"))


def get_default_diff_edit_command(editor: str) -> str:
    if editor in [
        "code",
        "vscode",
        "vscodium",
        "windsurf",
        "cursor",
        "zed",
        "zeditor",
        "agy",
    ]:
        return f"{editor} --wait --diff {{old}} {{new}}"
    if editor == "emacs":
        return 'emacs --eval \'(ediff-files "{old}" "{new}")\''
    if editor in ["nvim", "vim"]:
        return (
            f"{editor} -d {{old}} {{new}} "
            "-i NONE "
            '-c "wincmd h | set readonly | wincmd l" '
            '-c "highlight DiffAdd cterm=bold ctermbg=22 guibg=#005f00 | highlight DiffChange cterm=bold ctermbg=24 guibg=#005f87 | highlight DiffText ctermbg=21 guibg=#0000af | highlight DiffDelete ctermbg=52 guibg=#5f0000" '  # noqa
            '-c "set showtabline=2 | set tabline=[Instructions]\\ :wqa(save\\ &\\ quit)\\ \\|\\ i/esc(toggle\\ edit\\ mode)" '  # noqa
            '-c "wincmd h | setlocal statusline=OLD\\ FILE" '
            '-c "wincmd l | setlocal statusline=%#StatusBold#NEW\\ FILE\\ :wqa(save\\ &\\ quit)\\ \\|\\ i/esc(toggle\\ edit\\ mode)" '  # noqa
            '-c "autocmd BufWritePost * wqa"'
        )
    return 'vimdiff {old} {new} +"setlocal ro" +"wincmd l" +"autocmd BufWritePost <buffer> qa"'  # noqa


def get_log_level(level: str) -> int:
    level = level.upper()
    log_levels = {
        "CRITICAL": logging.CRITICAL,  # 50
        "FATAL": logging.CRITICAL,  # 50
        "ERROR": logging.ERROR,  # 40
        "WARN": logging.WARNING,  # 30
        "WARNING": logging.WARNING,  # 30
        "INFO": logging.INFO,  # 20
        "DEBUG": logging.DEBUG,  # 10
        "NOTSET": logging.NOTSET,  # 0
    }
    if level in log_levels:
        return log_levels[level]
    return logging.WARNING


def get_max_token_threshold(
    factor: float, max_tokens_per_minute: int, max_tokens_per_request: int
) -> int:
    return round(factor * min(max_tokens_per_minute, max_tokens_per_request))


def limit_token_threshold(
    threshold: int,
    factor: float,
    max_tokens_per_minute: int,
    max_tokens_per_request: int,
) -> int:
    return min(
        threshold,
        get_max_token_threshold(factor, max_tokens_per_minute, max_tokens_per_request),
    )
