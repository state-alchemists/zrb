from zrb.config.config import DEFAULT_SHELL
from zrb.task_input.str_input import StrInput

terminal_config_file_input = StrInput(
    name="config-file",
    shortcut="c",
    prompt="Config file",
    default="~/.zshrc" if DEFAULT_SHELL == "zsh" else "~/.bashrc",
)
