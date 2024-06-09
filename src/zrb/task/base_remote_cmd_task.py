import os
import pathlib

from zrb.helper.accessories.color import colored
from zrb.helper.log import logger
from zrb.helper.typecheck import typechecked
from zrb.helper.typing import (
    Any,
    Callable,
    Iterable,
    JinjaTemplate,
    Mapping,
    Optional,
    TypeVar,
    Union,
)
from zrb.helper.util import to_snake_case
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
from zrb.task.cmd_task import CmdTask, CmdVal
from zrb.task_env.env import Env
from zrb.task_env.env_file import EnvFile
from zrb.task_group.group import Group
from zrb.task_input.any_input import AnyInput

logger.debug(colored("Loading zrb.task.base_remote_cmd_task", attrs=["dark"]))

TSingleBaseRemoteCmdTask = TypeVar(
    "TSingleBaseRemoteCmdTask", bound="SingleBaseRemoteCmdTask"
)
TBaseRemoteCmdTask = TypeVar("TBaseRemoteCmdTask", bound="BaseRemoteCmdTask")


@typechecked
class RemoteConfig:
    def __init__(
        self,
        host: JinjaTemplate,
        user: JinjaTemplate = "",
        password: JinjaTemplate = "",
        ssh_key: JinjaTemplate = "",
        port: Union[int, JinjaTemplate] = 22,
        name: Optional[str] = None,
        config_map: Optional[Mapping[str, JinjaTemplate]] = None,
    ):
        self.name = name if name is not None else host
        self.host = host
        self.user = user
        self.password = password
        self.ssh_key = ssh_key
        self.port = port
        self.config_map = {} if config_map is None else config_map


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
        description: str = "",
        executable: Optional[str] = None,
        pre_cmd: CmdVal = "",
        pre_cmd_path: CmdVal = "",
        cmd: CmdVal = "",
        cmd_path: CmdVal = "",
        post_cmd: CmdVal = "",
        post_cmd_path: CmdVal = "",
        cwd: Optional[Union[str, pathlib.Path]] = None,
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
        preexec_fn: Optional[Callable[[], Any]] = os.setsid,
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
            preexec_fn=preexec_fn,
            should_execute=should_execute,
            return_upstream_result=return_upstream_result,
            should_print_cmd_result=should_print_cmd_result,
            should_show_cmd=should_show_cmd,
            should_show_working_directory=should_show_working_directory,
        )
        self._pre_cmd = pre_cmd
        self._pre_cmd_path = pre_cmd_path
        self._post_cmd = post_cmd
        self._post_cmd_path = post_cmd_path
        self._remote_config = remote_config

    def copy(self) -> TSingleBaseRemoteCmdTask:
        return super().copy()

    def inject_envs(self):
        super().inject_envs()
        # add remote config properties as env
        self.add_env(
            Env(
                name="_CONFIG_HOST",
                os_name="",
                default=self.render_str(self._remote_config.host),
            ),
            Env(
                name="_CONFIG_PORT",
                os_name="",
                default=str(self.render_int(self._remote_config.port)),
            ),
            Env(
                name="_CONFIG_SSH_KEY",
                os_name="",
                default=self.render_str(self._remote_config.ssh_key),
            ),
            Env(
                name="_CONFIG_USER",
                os_name="",
                default=self.render_str(self._remote_config.user),
            ),
            Env(
                name="_CONFIG_PASSWORD",
                os_name="",
                default=self.render_str(self._remote_config.password),
            ),
        )
        for key, val in self._remote_config.config_map.items():
            upper_snake_key = to_snake_case(key).upper()
            rendered_val = self.render_str(val)
            # add remote config map as env
            self.add_env(
                Env(
                    name="_CONFIG_MAP_" + upper_snake_key,
                    os_name="",
                    default=rendered_val,
                )
            )

    def get_cmd_script(self, *args: Any, **kwargs: Any) -> str:
        cmd_str = "\n".join(
            [
                self._create_cmd_script(
                    self._pre_cmd_path, self._pre_cmd, *args, **kwargs
                ),
                super().get_cmd_script(*args, **kwargs),
                self._create_cmd_script(
                    self._post_cmd_path, self._post_cmd, *args, **kwargs
                ),
            ]
        )
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
        description: str = "",
        executable: Optional[str] = None,
        pre_cmd: CmdVal = "",
        pre_cmd_path: CmdVal = "",
        cmd: CmdVal = "",
        cmd_path: CmdVal = "",
        post_cmd: CmdVal = "",
        post_cmd_path: CmdVal = "",
        cwd: Optional[Union[str, pathlib.Path]] = None,
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
        preexec_fn: Optional[Callable[[], Any]] = os.setsid,
        should_execute: Union[bool, str, Callable[..., bool]] = True,
        return_upstream_result: bool = False,
        should_print_cmd_result: bool = True,
        should_show_cmd: bool = True,
        should_show_working_directory: bool = True,
    ):
        self._remote_configs = list(remote_configs)
        self._sub_tasks = [
            SingleBaseRemoteCmdTask(
                name=f"{name}-{remote_config.name}",
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
                preexec_fn=preexec_fn,
                should_execute=should_execute,
                return_upstream_result=return_upstream_result,
                should_print_cmd_result=should_print_cmd_result,
                should_show_cmd=should_show_cmd,
                should_show_working_directory=should_show_working_directory,
            )
            for remote_config in self._remote_configs
        ]
        BaseTask.__init__(
            self,
            name=name,
            icon=icon,
            color=color,
            group=group,
            description=description,
            upstreams=self._sub_tasks,
            retry=0,
            return_upstream_result=True,
        )

    def insert_input(self, *inputs: AnyInput):
        super().insert_input(*inputs)
        for subtask in self._sub_tasks:
            subtask.insert_input(*inputs)

    def add_input(self, *inputs: AnyInput):
        super().add_input(*inputs)
        for subtask in self._sub_tasks:
            subtask.add_input(*inputs)

    def insert_env(self, *envs: Env):
        super().insert_env(*envs)
        for subtask in self._sub_tasks:
            subtask.insert_env(*envs)

    def add_env(self, *envs: Env):
        super().add_env(*envs)
        for subtask in self._sub_tasks:
            subtask.add_env(*envs)

    def insert_env_file(self, *env_files: EnvFile):
        super().insert_env_file(*env_files)
        for subtask in self._sub_tasks:
            subtask.insert_env_file(*env_files)

    def add_env_file(self, *env_files: Env):
        super().add_env_file(*env_files)
        for subtask in self._sub_tasks:
            subtask.add_env_file(*env_files)

    def insert_upstream(self, *upstreams: AnyTask):
        for subtask in self._sub_tasks:
            subtask.insert_upstream(*upstreams)

    def add_upstream(self, *upstreams: AnyTask):
        for subtask in self._sub_tasks:
            subtask.add_upstream(*upstreams)

    def insert_fallback(self, *fallbacks: AnyTask):
        for subtask in self._sub_tasks:
            subtask.insert_fallbacks(*fallbacks)

    def add_fallback(self, *fallbacks: AnyTask):
        for subtask in self._sub_tasks:
            subtask.add_fallback(*fallbacks)

    def insert_checker(self, *checkers: AnyTask):
        for subtask in self._sub_tasks:
            subtask.insert_checkers(*checkers)

    def add_checker(self, *checkers: AnyTask):
        for subtask in self._sub_tasks:
            subtask.add_checker(*checkers)
