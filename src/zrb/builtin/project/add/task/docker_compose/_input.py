from zrb.task_input.int_input import IntInput
from zrb.task_input.str_input import StrInput

http_port_input = IntInput(
    name="http-port",
    shortcut="p",
    description="HTTP port",
    prompt="HTTP port",
    default=8080,
)

compose_command_input = StrInput(
    name="compose-command",
    shortcut="c",
    description="Compose command",
    prompt="Compose command",
    default="up",
)
