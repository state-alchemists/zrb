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

    `shutil.which("bash")` finds `System32\\bash.exe`, the WSL launcher,
    which is not a usable shell here. Git for Windows' bash is located from
    `git` on PATH, then the standard install roots, then PATH (rejecting hits
    under the Windows directory). Returns "" on non-Windows platforms.

    Cached: `CFG.SHELL` reads hit this on every command. Tests stubbing
    `shutil.which`/`os.path.isfile` need `cache_clear()` (`conftest` does it).
    """
    if platform.system() != "Windows":
        return ""
    # `ntpath` keeps the lookup testable from any platform.
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
    """Whether *path* sits under the Windows directory, where the only `bash`
    is the WSL launcher."""
    system_root = os.getenv("SystemRoot") or "C:\\Windows"
    prefix = ntpath.normcase(system_root).rstrip("\\") + "\\"
    return ntpath.normcase(path).startswith(prefix)


_EXE_SUFFIX = re.compile(r"\.exe$", re.IGNORECASE)


def get_shell_name(shell: str) -> str:
    """The bare shell name behind a shell setting: `bash` for `bash`,
    `/bin/bash` and `C:\\Program Files\\Git\\bin\\bash.exe` alike.

    Compare shell settings through this: on Windows they are absolute `.exe`
    paths. Both separators are split on, whatever the running platform.
    """
    return _EXE_SUFFIX.sub("", re.split(r"[\\/]", shell)[-1]).lower()


def get_current_shell() -> str:
    """Return the name of a shell that actually exists on this system.

    Names are verified with ``shutil.which``; the final fallbacks (``sh`` /
    ``cmd``) are effectively always present.
    """
    if platform.system() == "Windows":
        # zrb's own shell commands are POSIX, so prefer Git Bash.
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

    Checks ``TERMUX_VERSION``, a ``com.termux`` ``PREFIX``, then
    ``ANDROID_ROOT=/system`` (proot distros lose the first two).
    """
    if os.getenv("TERMUX_VERSION"):
        return True
    if "com.termux" in os.getenv("PREFIX", ""):
        return True
    if os.getenv("ANDROID_ROOT") == "/system":
        return True
    return False


def is_wsl() -> bool:
    """Best-effort detection of WSL (``WSL_DISTRO_NAME`` or ``WSLENV``)."""
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
