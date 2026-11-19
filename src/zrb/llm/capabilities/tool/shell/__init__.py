"""The shell tools: one command, the processes it leaves behind, and their output."""

from zrb.llm.capabilities.tool.shell.background import (
    BackgroundProcessRow,
    create_monitor_process_tool,
    get_shell_background_registry,
)
from zrb.llm.capabilities.tool.shell.capture import StreamCapture
from zrb.llm.capabilities.tool.shell.command import run_shell_command, start_process

__all__ = [
    "BackgroundProcessRow",
    "StreamCapture",
    "create_monitor_process_tool",
    "get_shell_background_registry",
    "run_shell_command",
    "start_process",
]
