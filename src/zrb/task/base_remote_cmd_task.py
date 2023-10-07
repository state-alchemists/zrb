from zrb.helper.typing import (
    Any, Callable, Iterable, Mapping, Optional, Union, TypeVar
)
from zrb.helper.typecheck import typechecked
from zrb.task.any_task import AnyTask
from zrb.task.base_task import BaseTask
from zrb.task_env.env import Env
from zrb.task_env.env_file import EnvFile
from zrb.task_group.group import Group
from zrb.task_input.any_input import AnyInput
from zrb.task.cmd_task import CmdTask, CmdVal

import copy
import os
import pathlib


TSingleBaseRemoteCmdTask = TypeVar(
    'TSingleBaseRemoteCmdTask', bound='SingleBaseRemoteCmdTask'
)
TBaseRemoteCmdTask = TypeVar(
    'TBaseRemoteCmdTask', bound='BaseRemoteCmdTask'
)


@typechecked
class RemoteConfig:
    def __init__(
        self,
        host: str,
        user: str = '',
        password: str = '',
        ssh_key: str = '',
        port: int = 22
    ):
        self.host = host
        self.user = user
        self.password = password
        self.ssh_key = ssh_key
        self.port = port


@typechecked
class SingleBaseRemoteCmdTask(CmdTask):
    def __init__(
        self,
        name: str,
        remote_config: RemoteConfig,
        group: Optional[Group] = None,
        inputs: Iterable[AnyInput] = [],
        envs: Iterable[Env] = [],
        env_files: Iterable[EnvFile] = [],
        icon: Optional[str] = None,
        color: Optional[str] = None,
        description: str = '',
        executable: Optional[str] = None,
        pre_cmd: CmdVal = '',
        pre_cmd_path: CmdVal = '',
        cmd: CmdVal = '',
        cmd_path: CmdVal = '',
        post_cmd: CmdVal = '',
        post_cmd_path: CmdVal = '',
        cwd: Optional[Union[str, pathlib.Path]] = None,
        upstreams: Iterable[AnyTask] = [],
        checkers: Iterable[AnyTask] = [],
        checking_interval: Union[float, int] = 0,
        retry: int = 2,
        retry_interval: Union[float, int] = 1,
        max_output_line: int = 1000,
        max_error_line: int = 1000,
        preexec_fn: Optional[Callable[[], Any]] = os.setsid,
        skip_execution: Union[bool, str, Callable[..., bool]] = False,
        return_upstream_result: bool = False
    ):
        CmdTask.__init__(
            self,
            name=name,
            group=group,
            inputs=inputs,
            envs=envs,
            env_files=env_files,
            icon=icon,
            color=color,
            description=description,
            executable=executable,
            cmd=cmd,
            cmd_path=cmd_path,
            cwd=cwd,
            upstreams=upstreams,
            checkers=checkers,
            checking_interval=checking_interval,
            retry=retry,
            retry_interval=retry_interval,
            max_output_line=max_output_line,
            max_error_line=max_error_line,
            preexec_fn=preexec_fn,
            skip_execution=skip_execution,
            return_upstream_result=return_upstream_result
        )
        self._pre_cmd = pre_cmd
        self._pre_cmd_path = pre_cmd_path
        self._post_cmd = post_cmd
        self._post_cmd_path = post_cmd_path
        self._remote_config = remote_config

    def copy(self) -> TSingleBaseRemoteCmdTask:
        return copy.deepcopy(self)

    def _get_shell_env_map(self) -> Mapping[str, Any]:
        env_map = super()._get_shell_env_map()
        env_map['_CONFIG_HOST'] = self.render_str(self._remote_config.host)
        env_map['_CONFIG_PORT'] = str(self.render_int(
            self._remote_config.port)
        )
        env_map['_CONFIG_SSH_KEY'] = self.render_str(
            self._remote_config.ssh_key
        )
        env_map['_CONFIG_USER'] = self.render_str(self._remote_config.user)
        env_map['_CONFIG_PASSWORD'] = self.render_str(
            self._remote_config.password
        )
        return env_map

    def _get_cmd_str(self, *args: Any, **kwargs: Any) -> str:
        cmd_str = '\n'.join([
            self._create_cmd_str(
                self._pre_cmd_path, self._pre_cmd, *args, **kwargs
            ),
            super()._get_cmd_str(*args, **kwargs),
            self._create_cmd_str(
                self._post_cmd_path, self._post_cmd, *args, **kwargs
            ),
        ])
        return cmd_str


@typechecked
class BaseRemoteCmdTask(BaseTask):
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
        pre_cmd: CmdVal = '',
        pre_cmd_path: CmdVal = '',
        cmd: CmdVal = '',
        cmd_path: CmdVal = '',
        post_cmd: CmdVal = '',
        post_cmd_path: CmdVal = '',
        cwd: Optional[Union[str, pathlib.Path]] = None,
        upstreams: Iterable[AnyTask] = [],
        checkers: Iterable[AnyTask] = [],
        checking_interval: Union[float, int] = 0,
        retry: int = 2,
        retry_interval: Union[float, int] = 1,
        max_output_line: int = 1000,
        max_error_line: int = 1000,
        preexec_fn: Optional[Callable[[], Any]] = os.setsid,
        skip_execution: Union[bool, str, Callable[..., bool]] = False,
        return_upstream_result: bool = False
    ):
        sub_tasks = [
            SingleBaseRemoteCmdTask(
                name=f'{name}-{remote_config.host}',
                remote_config=remote_config,
                inputs=inputs,
                envs=envs,
                env_files=env_files,
                description=description,
                executable=executable,
                pre_cmd=pre_cmd,
                pre_cmd_path=pre_cmd_path,
                cmd=cmd,
                cmd_path=cmd_path,
                post_cmd=post_cmd,
                post_cmd_path=post_cmd_path,
                cwd=cwd,
                upstreams=upstreams,
                checkers=checkers,
                checking_interval=checking_interval,
                retry=retry,
                retry_interval=retry_interval,
                max_output_line=max_output_line,
                max_error_line=max_error_line,
                preexec_fn=preexec_fn,
                skip_execution=skip_execution,
                return_upstream_result=return_upstream_result
            )
            for remote_config in list(remote_configs)
        ]
        BaseTask.__init__(
            self,
            name=name,
            icon=icon,
            color=color,
            group=group,
            description=description,
            upstreams=sub_tasks,
            retry=0,
            return_upstream_result=True
        )
