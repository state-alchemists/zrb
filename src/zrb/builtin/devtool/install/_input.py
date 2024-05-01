from zrb.config.config import default_shell
from zrb.task_input.str_input import StrInput

terminal_config_file_input = StrInput(
    name="config-file",
    shortcut="c",
    prompt="Config file",
    default="~/.zshrc" if default_shell == "zsh" else "~/.bashrc",
)
