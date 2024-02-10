import os
import subprocess

from zrb.helper.accessories.icon import get_random_icon
from zrb.helper.string.modification import double_quote
from zrb.helper.typecheck import typechecked
from zrb.helper.typing import Any, Callable, Iterable, JinjaTemplate, Optional, Union
from zrb.task.any_task import AnyTask
from zrb.task.any_task_event_handler import (
    OnFailed,
    OnReady,
    OnRetry,
    OnSkipped,
    OnStarted,
    OnTriggered,
    OnWaiting,
)
from zrb.task.base_task.base_task import BaseTask
from zrb.task_env.env import Env
from zrb.task_env.env_file import EnvFile
from zrb.task_group.group import Group
from zrb.task_input.any_input import AnyInput

CURRENT_DIR = os.path.dirname(__file__)
NOTIFY_PS1_PATH = os.path.realpath(
    os.path.abspath(
        os.path.join(os.path.dirname(CURRENT_DIR), "shell-scripts", "notify.ps1")
    )
)


@typechecked
class Notifier(BaseTask):
    def __init__(
        self,
        name: str = "port-check",
        group: Optional[Group] = None,
        inputs: Iterable[AnyInput] = [],
        envs: Iterable[Env] = [],
        env_files: Iterable[EnvFile] = [],
        icon: Optional[str] = None,
        color: Optional[str] = None,
        description: str = "",
        title: JinjaTemplate = "",
        message: JinjaTemplate = "",
        show_toast: bool = True,
        show_stdout: bool = True,
        upstreams: Iterable[AnyTask] = [],
        on_triggered: Optional[OnTriggered] = None,
        on_waiting: Optional[OnWaiting] = None,
        on_skipped: Optional[OnSkipped] = None,
        on_started: Optional[OnStarted] = None,
        on_ready: Optional[OnReady] = None,
        on_retry: Optional[OnRetry] = None,
        on_failed: Optional[OnFailed] = None,
        checking_interval: Union[int, float] = 0,
        retry: int = 2,
        retry_interval: Union[float, int] = 1,
        should_execute: Union[bool, str, Callable[..., bool]] = True,
    ):
        BaseTask.__init__(
            self,
            name=name,
            group=group,
            inputs=inputs,
            envs=envs,
            env_files=env_files,
            icon=icon,
            color=color,
            description=description,
            upstreams=upstreams,
            on_triggered=on_triggered,
            on_waiting=on_waiting,
            on_skipped=on_skipped,
            on_started=on_started,
            on_ready=on_ready,
            on_retry=on_retry,
            on_failed=on_failed,
            checkers=[],
            checking_interval=checking_interval,
            retry=retry,
            retry_interval=retry_interval,
            should_execute=should_execute,
        )
        self._title = title if title != "" else name
        self._message = message if message != "" else get_random_icon()
        self._show_toast = show_toast
        self._show_stdout = show_stdout

    async def run(self, *args: Any, **kwargs: Any) -> str:
        title = self.render_str(self._title)
        message = self.render_str(self._message)
        notify_kwargs = {
            key: value
            for key, value in kwargs.items()
            if key not in ("title", "message")
        }
        await self.notify(title, message, **notify_kwargs)
        return message

    async def notify(self, title: str, message: str, **kwargs: Any) -> None:
        task: BaseTask = kwargs.get("_task")
        if self._show_toast and _is_powershell_available():
            cmd = [
                "powershell.exe",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                NOTIFY_PS1_PATH,
                "-Title",
                title,
                "-Message",
                message,
            ]
            subprocess.run(cmd, stdout=subprocess.DEVNULL)
        if self._show_toast and _is_osascript_available():
            q_message = double_quote(message)
            q_title = double_quote(title)
            cmd = [
                "osascript",
                "-e",
                f'display notification "{q_message}" with title "{q_title}"',
            ]
        if self._show_toast and _is_notify_send_available():
            cmd = ["notify-send", title, message]
            subprocess.run(cmd, stdout=subprocess.DEVNULL)
        if self._show_toast and _is_termux_notification_available():
            cmd = ["termux-notification", "-t", title, "-c", message, "--sound"]
            subprocess.run(cmd, stdout=subprocess.DEVNULL)
        if self._show_stdout:
            task.print_out(message)
            task._play_bell()


def _is_powershell_available():
    try:
        subprocess.run(
            ["powershell.exe", "-Command", 'echo "Checking PowerShell"'],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError, PermissionError):
        return False


def _is_termux_notification_available():
    try:
        subprocess.run(
            ["termux-notification", "--help"],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError, PermissionError):
        return False


def _is_notify_send_available():
    try:
        subprocess.run(
            ["notify-send", "--version"],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError, PermissionError):
        return False


def _is_osascript_available():
    try:
        subprocess.run(
            ["osascript", "-e", "return"],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError, PermissionError):
        return False
