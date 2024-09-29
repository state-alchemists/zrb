import os
import pathlib
from collections.abc import Callable, Iterable, Mapping
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
from zrb.task.cmd_task import CmdVal
from zrb.task.docker_compose_task import DockerComposeTask, ServiceConfig
from zrb.task_env.env import Env
from zrb.task_env.env_file import EnvFile
from zrb.task_group.group import Group
from zrb.task_input.any_input import AnyInput

logger.debug(colored("Loading zrb.task.docker_compose_task", attrs=["dark"]))


@typechecked
class DockerComposeStartTask(DockerComposeTask):
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
        compose_service_configs: Mapping[str, ServiceConfig] = {},
        compose_file: Optional[str] = None,
        compose_options: Mapping[JinjaTemplate, JinjaTemplate] = {},
        compose_flags: Iterable[JinjaTemplate] = [],
        compose_args: Iterable[JinjaTemplate] = [],
        compose_profiles: Iterable[JinjaTemplate] = [],
        compose_env_prefix: str = "",
        setup_cmd: CmdVal = "",
        setup_cmd_path: CmdVal = "",
        cwd: Optional[Union[JinjaTemplate, pathlib.Path]] = None,
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
        preexec_fn: Optional[Callable[[], Any]] = os.setsid,
        should_execute: Union[bool, str, Callable[..., bool]] = True,
        return_upstream_result: bool = False,
        should_print_cmd_result: bool = True,
        should_show_cmd: bool = True,
        should_show_working_directory: bool = True,
    ):
        DockerComposeTask.__init__(
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
            compose_service_configs=compose_service_configs,
            compose_file=compose_file,
            compose_cmd="up",
            compose_options=compose_options,
            compose_flags=compose_flags,
            compose_args=compose_args,
            compose_profiles=compose_profiles,
            compose_env_prefix=compose_env_prefix,
            setup_cmd=setup_cmd,
            setup_cmd_path=setup_cmd_path,
            cwd=cwd,
            should_render_cwd=should_render_cwd,
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

    def _get_execute_docker_compose_script(
        self,
        compose_cmd: JinjaTemplate,
        compose_options: Mapping[JinjaTemplate, JinjaTemplate],
        compose_flags: Iterable[JinjaTemplate],
        compose_args: Iterable[JinjaTemplate],
        *args: Any
    ) -> JinjaTemplate:
        return "\n".join(
            [
                # compose start
                super()._get_execute_docker_compose_script(
                    compose_cmd=compose_cmd,
                    compose_options=compose_options,
                    compose_flags=list(compose_flags) + ["-d"],
                    compose_args=compose_args,
                    *args,
                ),
                # compose log
                super()._get_execute_docker_compose_script(
                    compose_cmd="logs",
                    compose_options={},
                    compose_flags=["-f"],
                    compose_args=[],
                    *args,
                ),
            ]
        )
