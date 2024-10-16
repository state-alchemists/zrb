import os
import pathlib
from collections.abc import Callable, Iterable
from typing import Any, Optional, Union

from zrb.helper.accessories.color import colored
from zrb.helper.log import logger
from zrb.helper.typecheck import typechecked
from zrb.helper.typing import JinjaTemplate
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
from zrb.task.cmd_task import CmdTask, CmdVal
from zrb.task_env.env import Env, PrivateEnv
from zrb.task_env.env_file import EnvFile
from zrb.task_group.group import Group
from zrb.task_input.any_input import AnyInput

logger.debug(colored("Loading zrb.task.remote_cmd_task", attrs=["dark"]))

_CURRENT_DIR = os.path.dirname(__file__)
_SHELL_SCRIPT_DIR = os.path.join(_CURRENT_DIR, "..", "shell-scripts")

ensure_ssh_is_installed = CmdTask(
    name="ensure-ssh-is-installed",
    cmd_path=[
        os.path.join(_SHELL_SCRIPT_DIR, "_common-util.sh"),
        os.path.join(_SHELL_SCRIPT_DIR, "ensure-ssh-is-installed.sh"),
    ],
    should_print_cmd_result=False,
    should_show_cmd=False,
    should_show_working_directory=False,
)


@typechecked
class RemoteCmdTask(CmdTask):
    def __init__(
        self,
        name: str,
        group: Optional[Group] = None,
        inputs: Iterable[AnyInput] = [],
        envs: Iterable[Env] = [],
        env_files: Iterable[EnvFile] = [],
        icon: Optional[str] = None,
        color: Optional[str] = None,
        description: str = "",
        executable: Optional[str] = None,
        remote_host: JinjaTemplate = "localhost",
        remote_port: Union[JinjaTemplate, int] = 22,
        remote_user: JinjaTemplate = "root",
        remote_password: JinjaTemplate = "",
        remote_ssh_key: JinjaTemplate = "",
        cmd: CmdVal = "",
        cmd_path: CmdVal = "",
        cwd: Optional[Union[str, pathlib.Path]] = None,
        should_render_cwd: bool = True,
        upstreams: Iterable[AnyTask] = [],
        fallbacks: Iterable[AnyTask] = [],
        on_triggered: Optional[OnTriggered] = None,
        on_waiting: Optional[OnWaiting] = None,
        on_skipped: Optional[OnSkipped] = None,
        on_started: Optional[OnStarted] = None,
        on_ready: Optional[OnReady] = None,
        on_retry: Optional[OnRetry] = None,
        on_failed: Optional[OnFailed] = None,
        checkers: Iterable[AnyTask] = [],
        checking_interval: Union[float, int] = 0.05,
        retry: int = 2,
        retry_interval: Union[float, int] = 1,
        max_output_line: int = 1000,
        max_error_line: int = 1000,
        should_execute: Union[bool, str, Callable[..., bool]] = True,
        return_upstream_result: bool = False,
        should_print_cmd_result: bool = True,
        should_show_cmd: bool = True,
        should_show_working_directory: bool = True,
    ):
        CmdTask.__init__(
            self,
            name=name,
            group=group,
            inputs=inputs,
            envs=envs + [PrivateEnv(name="_ZRB_SSH_PASSWORD", default=remote_password)],
            env_files=env_files,
            icon=icon,
            color=color,
            description=description,
            executable=executable,
            cmd=cmd,
            cmd_path=cmd_path,
            cwd=cwd,
            should_render_cwd=should_render_cwd,
            upstreams=[ensure_ssh_is_installed] + upstreams,
            fallbacks=fallbacks,
            on_triggered=on_triggered,
            on_waiting=on_waiting,
            on_skipped=on_skipped,
            on_started=on_started,
            on_ready=on_ready,
            on_retry=on_retry,
            on_failed=on_failed,
            checkers=checkers,
            checking_interval=checking_interval,
            retry=retry,
            retry_interval=retry_interval,
            max_output_line=max_output_line,
            max_error_line=max_error_line,
            should_execute=should_execute,
            return_upstream_result=return_upstream_result,
            should_print_cmd_result=should_print_cmd_result,
            should_show_cmd=should_show_cmd,
            should_show_working_directory=should_show_working_directory,
        )
        self._remote_host = remote_host
        self._remote_port = remote_port
        self._remote_user = remote_user
        self._remote_password = remote_password
        self._remote_ssh_key = remote_ssh_key

    def get_cmd_script(self, *args: Any, **kwargs: Any) -> str:
        cmd_script = self._create_cmd_script(self._cmd_path, self._cmd, *args, **kwargs)
        cmd_script = "\n".join(
            [
                "_SCRIPT=$(cat << 'ENDSCRIPT'",
                cmd_script,
                "ENDSCRIPT",
                ")",
            ]
        )
        ssh_command = self._get_ssh_command()
        return "\n".join([cmd_script, ssh_command])

    def _get_ssh_command(self) -> str:
        host = self.render_str(self._remote_host)
        port = self.render_str(self._remote_port)
        user = self.render_str(self._remote_user)
        password = self.render_str(self._remote_password)
        key = self.render_str(self._remote_ssh_key)
        if key != "" and password != "":
            return f'sshpass -p "$_ZRB_SSH_PASSWORD" ssh -t -p "{port}" -i "{key}" "{user}@{host}" "$_SCRIPT"'  # noqa
        if key != "":
            return f'ssh -t -p "{port}" -i "{key}" "{user}@{host}" "$_SCRIPT"'
        if password != "":
            return f'sshpass -p "$_ZRB_SSH_PASSWORD" ssh -t -p "{port}" "{user}@{host}" "$_SCRIPT"'  # noqa
        return f'ssh -t -p "{port}" "{user}@{host}" "$_SCRIPT"'
