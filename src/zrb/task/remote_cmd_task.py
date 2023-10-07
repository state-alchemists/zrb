from zrb.helper.typing import Any, Callable, Iterable, Optional, Union
from zrb.helper.typecheck import typechecked
from zrb.task.any_task import AnyTask
from zrb.task_env.env import Env
from zrb.task_env.env_file import EnvFile
from zrb.task_group.group import Group
from zrb.task_input.any_input import AnyInput
from zrb.task.cmd_task import CmdVal, CmdTask
from zrb.task.base_remote_cmd_task import RemoteConfig, BaseRemoteCmdTask

import os
import pathlib


CURRENT_DIR = os.path.dirname(__file__)
SHELL_SCRIPT_DIR = os.path.join(CURRENT_DIR, '..', 'shell-scripts')
with open(os.path.join(SHELL_SCRIPT_DIR, 'ssh-util.sh')) as file:
    SSH_UTIL_SCRIPT = file.read()

ensure_ssh_is_installed = CmdTask(
    name='ensure-ssh-is-installed',
    cmd_path=[
        os.path.join(SHELL_SCRIPT_DIR, '_common-util.sh'),
        os.path.join(SHELL_SCRIPT_DIR, 'ensure-ssh-is-installed.sh')
    ],
    preexec_fn=None
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
        description: str = '',
        executable: Optional[str] = None,
        cmd: CmdVal = '',
        cmd_path: CmdVal = '',
        cwd: Optional[Union[str, pathlib.Path]] = None,
        upstreams: Iterable[AnyTask] = [],
        checkers: Iterable[AnyTask] = [],
        checking_interval: Union[float, int] = 0,
        retry: int = 2,
        retry_interval: Union[float, int] = 1,
        max_output_line: int = 1000,
        max_error_line: int = 1000,
        preexec_fn: Optional[Callable[[], Any]] = os.setsid,
        skip_execution: Union[bool, str, Callable[..., bool]] = False
    ):
        pre_cmd = '\n'.join([
            SSH_UTIL_SCRIPT,
            '_SCRIPT="$(cat <<\'ENDSCRIPT\'',
        ])
        post_cmd = '\n'.join([
            'ENDSCRIPT',
            ')"',
            'auth_ssh "$_SCRIPT"'
        ])
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
            checkers=checkers,
            checking_interval=checking_interval,
            retry=retry,
            retry_interval=retry_interval,
            max_output_line=max_output_line,
            max_error_line=max_error_line,
            preexec_fn=preexec_fn,
            skip_execution=skip_execution
        )

    def __repr__(self) -> str:
        return f'<RemoteCmdTask name={self._name}>'
