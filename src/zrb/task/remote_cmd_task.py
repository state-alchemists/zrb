import os
import pathlib

from zrb.helper.typecheck import typechecked
from zrb.helper.typing import Any, Callable, Iterable, Optional, Union
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
from zrb.task.base_remote_cmd_task import BaseRemoteCmdTask, RemoteConfig
from zrb.task.cmd_task import CmdTask, CmdVal
from zrb.task_env.env import Env
from zrb.task_env.env_file import EnvFile
from zrb.task_group.group import Group
from zrb.task_input.any_input import AnyInput

CURRENT_DIR = os.path.dirname(__file__)
SHELL_SCRIPT_DIR = os.path.join(CURRENT_DIR, "..", "shell-scripts")
with open(os.path.join(SHELL_SCRIPT_DIR, "ssh-util.sh")) as file:
    SSH_UTIL_SCRIPT = file.read()

ensure_ssh_is_installed = CmdTask(
    name="ensure-ssh-is-installed",
    cmd_path=[
        os.path.join(SHELL_SCRIPT_DIR, "_common-util.sh"),
        os.path.join(SHELL_SCRIPT_DIR, "ensure-ssh-is-installed.sh"),
    ],
    preexec_fn=None,
)


@typechecked
class RemoteCmdTask(BaseRemoteCmdTask):
    def __init__(
        self,
        name: str,
        remote_configs: Iterable[RemoteConfig],
        group: Optional[Group] = None,
        inputs: Iterable[AnyInput] = [],
        envs: Iterable[Env] = [],
        env_files: Iterable[EnvFile] = [],
        icon: Optional[str] = None,
        color: Optional[str] = None,
        description: str = "",
        executable: Optional[str] = None,
        cmd: CmdVal = "",
        cmd_path: CmdVal = "",
        cwd: Optional[Union[str, pathlib.Path]] = None,
        upstreams: Iterable[AnyTask] = [],
        on_triggered: Optional[OnTriggered] = None,
        on_waiting: Optional[OnWaiting] = None,
        on_skipped: Optional[OnSkipped] = None,
        on_started: Optional[OnStarted] = None,
        on_ready: Optional[OnReady] = None,
        on_retry: Optional[OnRetry] = None,
        on_failed: Optional[OnFailed] = None,
        checkers: Iterable[AnyTask] = [],
        checking_interval: Union[float, int] = 0,
        retry: int = 2,
        retry_interval: Union[float, int] = 1,
        max_output_line: int = 1000,
        max_error_line: int = 1000,
        preexec_fn: Optional[Callable[[], Any]] = os.setsid,
        should_execute: Union[bool, str, Callable[..., bool]] = True,
    ):
        pre_cmd = "\n".join(
            [
                SSH_UTIL_SCRIPT,
                "_SCRIPT=\"$(cat <<'ENDSCRIPT'",
            ]
        )
        post_cmd = "\n".join(["ENDSCRIPT", ')"', 'auth_ssh "$_SCRIPT"'])
        BaseRemoteCmdTask.__init__(
            self,
            name=name,
            remote_configs=remote_configs,
            group=group,
            inputs=inputs,
            envs=envs,
            env_files=env_files,
            icon=icon,
            color=color,
            description=description,
            executable=executable,
            pre_cmd=pre_cmd,
            cmd=cmd,
            cmd_path=cmd_path,
            post_cmd=post_cmd,
            cwd=cwd,
            upstreams=[ensure_ssh_is_installed] + upstreams,
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
            preexec_fn=preexec_fn,
            should_execute=should_execute,
        )
