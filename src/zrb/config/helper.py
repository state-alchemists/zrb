import logging
import os
import platform


def get_env(env_name: str | list[str], default: str = "", prefix: str = "ZRB") -> str:
    env_name_list = env_name if isinstance(env_name, list) else [env_name]
    for name in env_name_list:
        value = os.getenv(f"{prefix}_{name}", None)
        if value is not None:
            return value
    return default


def get_current_shell() -> str:
    if platform.system() == "Windows":
        return "PowerShell"
    current_shell = os.getenv("SHELL", "")
    if current_shell.endswith("zsh"):
        return "zsh"
    return "bash"


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
