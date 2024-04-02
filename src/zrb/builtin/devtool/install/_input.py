from zrb.config.config import get_current_shell
from zrb.task_input.str_input import StrInput

current_shell = get_current_shell()

terminal_config_file_input = StrInput(
    name="config-file",
    shortcut="c",
    prompt="Config file",
    default="~/.zshrc" if current_shell == "zsh" else "~/.bashrc",
)
