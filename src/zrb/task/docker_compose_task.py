import os
import pathlib
from collections.abc import Callable, Iterable, Mapping
from typing import Any, Optional, TypeVar, Union

from zrb.helper.accessories.color import colored
from zrb.helper.docker_compose.fetch_external_env import fetch_compose_file_env_map
from zrb.helper.docker_compose.file import read_compose_file
from zrb.helper.log import logger
from zrb.helper.string.modification import double_quote
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
from zrb.task_env.constant import RESERVED_ENV_NAMES
from zrb.task_env.env import Env
from zrb.task_env.env_file import EnvFile
from zrb.task_group.group import Group
from zrb.task_input.any_input import AnyInput

logger.debug(colored("Loading zrb.task.docker_compose_task", attrs=["dark"]))

TDockerComposeTask = TypeVar("TDockerComposeTask", bound="DockerComposeTask")

CURRENT_DIR = os.path.dirname(__file__)
SHELL_SCRIPT_DIR = os.path.join(CURRENT_DIR, "..", "shell-scripts")
ensure_docker_is_installed = CmdTask(
    name="ensure-docker-is-installed",
    cmd_path=[
        os.path.join(SHELL_SCRIPT_DIR, "_common-util.sh"),
        os.path.join(SHELL_SCRIPT_DIR, "ensure-docker-is-installed.sh"),
    ],
    should_print_cmd_result=False,
    should_show_cmd=False,
    should_show_working_directory=False,
)


@typechecked
class ServiceConfig:
    def __init__(self, envs: list[Env] = [], env_files: list[EnvFile] = []):
        self._envs = envs
        self._env_files = env_files

    def get_envs(self) -> list[Env]:
        return self._envs

    def get_env_files(self) -> list[EnvFile]:
        return self._env_files


@typechecked
class DockerComposeTask(CmdTask):
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
        remote_host: Optional[JinjaTemplate] = None,
        remote_port: Union[JinjaTemplate, int] = 22,
        remote_user: JinjaTemplate = "root",
        remote_password: JinjaTemplate = "",
        remote_ssh_key: JinjaTemplate = "",
        compose_service_configs: Mapping[str, ServiceConfig] = {},
        compose_file: Optional[str] = None,
        compose_cmd: str = "up",
        compose_options: Mapping[JinjaTemplate, JinjaTemplate] = {},
        compose_flags: Iterable[JinjaTemplate] = [],
        compose_args: Iterable[JinjaTemplate] = [],
        compose_profiles: CmdVal = "",
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
            remote_host=remote_host,
            remote_port=remote_port,
            remote_user=remote_user,
            remote_password=remote_password,
            remote_ssh_key=remote_ssh_key,
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
            should_execute=should_execute,
            return_upstream_result=return_upstream_result,
            should_print_cmd_result=should_print_cmd_result,
            should_show_cmd=should_show_cmd,
            should_show_working_directory=should_show_working_directory,
        )
        self._setup_cmd = setup_cmd
        self._setup_cmd_path = setup_cmd_path
        self._compose_service_configs = compose_service_configs
        self._compose_cmd = compose_cmd
        self._compose_options = compose_options
        if "--f" in compose_options:
            raise ValueError("compose option cannot contains --f")
        if "--file" in compose_options:
            raise ValueError("compose option cannot contains --file")
        self._compose_flags = compose_flags
        self._compose_args = compose_args
        self._compose_env_prefix = compose_env_prefix
        self._compose_profiles = compose_profiles
        self._compose_file = self.__get_compose_file(compose_file)
        # Flag to make mark whether service config and compose environments
        # has been added to this task's envs and env_files
        self._is_compose_additional_env_added = False
        self._is_compose_additional_env_file_added = False
        if self._remote_host is None:
            self.add_upstream(ensure_docker_is_installed)
        else:
            self.add_upstream(
                CmdTask(
                    name="ensure-remote-docker-is-installed",
                    cmd_path=[
                        os.path.join(SHELL_SCRIPT_DIR, "_common-util.sh"),
                        os.path.join(SHELL_SCRIPT_DIR, "ensure-docker-is-installed.sh"),
                    ],
                    remote_host=remote_host,
                    remote_port=remote_port,
                    remote_user=remote_user,
                    remote_password=remote_password,
                    remote_ssh_key=remote_ssh_key,
                    should_print_cmd_result=False,
                    should_show_cmd=False,
                    should_show_working_directory=False,
                )
            )

    def copy(self) -> TDockerComposeTask:
        return super().copy()

    def inject_envs(self):
        super().inject_envs()
        # inject envs from service_configs
        for _, service_config in self._compose_service_configs.items():
            self.insert_env(*service_config.get_envs())
        # inject envs from docker compose file
        compose_data = read_compose_file(self._compose_file)
        env_map = fetch_compose_file_env_map(compose_data)
        added_env_map: Mapping[str, bool] = {}
        for key, value in env_map.items():
            # Need to get this everytime because we only want
            # the first compose file env value for a certain key
            if key in RESERVED_ENV_NAMES or key in added_env_map:
                continue
            added_env_map[key] = True
            os_name = key
            if self._compose_env_prefix != "":
                os_name = f"{self._compose_env_prefix}_{os_name}"
            self.insert_env(Env(name=key, os_name=os_name, default=value))

    def inject_env_files(self):
        super().inject_env_files
        # inject env_files from service_configs
        for _, service_config in self._compose_service_configs.items():
            self.insert_env_file(*service_config.get_env_files())

    def __get_compose_file(self, compose_file: Optional[str]) -> str:
        if self._remote_host is None:
            cwd = self._cwd
            if compose_file is None:
                # Default compose files
                for name in ["compose", "docker-compose"]:
                    for ext in ["yaml", "yml"]:
                        compose_file = os.path.join(cwd, f"{name}.{ext}")
                        if os.path.exists(compose_file):
                            return compose_file
                # Default template compose files
                for name in ["compose", "docker-compose"]:
                    for ext in ["yaml", "yml"]:
                        compose_file = os.path.join(cwd, f"{name}.{ext}")
                        if os.path.exists(os.path.join(cwd, f"{name}.template.{ext}")):
                            return compose_file
                        if os.path.exists(os.path.join(cwd, f"{name}.tpl.{ext}")):
                            return compose_file
                return os.path.join(cwd, "docker-compose.yaml")
            if os.path.isabs(compose_file):
                return compose_file
            if os.path.join(cwd, compose_file):
                return os.path.join(cwd, compose_file)
        return "docker-compose.yml"

    def get_cmd_script(self, *args: Any, **kwargs: Any) -> str:
        cmd_list = []
        # create network
        create_network_script = self._get_create_compose_network_script()
        if create_network_script.strip() != "":
            cmd_list.append(create_network_script)
        # set compose profiles
        compose_profile_script = self._get_compose_profile_script(*args, **kwargs)
        if compose_profile_script.strip() != "":
            cmd_list.append(compose_profile_script)
        # setup
        setup_script = self._create_cmd_script(
            self._setup_cmd_path, self._setup_cmd, *args, **kwargs
        )
        if setup_script.strip() != "":
            cmd_list.append(setup_script)
        # compose command
        cmd_list.append(
            self._get_execute_docker_compose_script(
                compose_cmd=self._compose_cmd,
                compose_options=self._compose_options,
                compose_flags=self._compose_flags,
                compose_args=self._compose_args,
                *args,
            )
        )
        cmd_str = "\n".join(cmd_list)
        self.log_info(f"Command: {cmd_str}")
        return cmd_str

    def _get_compose_profile_script(self, *args, **kwargs) -> str:
        # Get list representation of self._compose_profiles
        compose_profiles = self._compose_profiles
        if callable(compose_profiles):
            compose_profiles = self._compose_profiles(*args, **kwargs)
        if isinstance(compose_profiles, str):
            compose_profiles = compose_profiles.split(",")
        # Get only non empty profiles
        filtered_compose_profiles = [
            self.render_str(profile)
            for profile in compose_profiles
            if self.render_str(profile).strip() != ""
        ]
        if len(filtered_compose_profiles) == 0:
            return ""
        compose_profiles_str = ",".join(filtered_compose_profiles)
        return f"export COMPOSE_PROFILES={compose_profiles_str}"

    def _get_create_compose_network_script(self) -> str:
        compose_data = read_compose_file(self._compose_file)
        networks: Mapping[str, Mapping[str, Any]] = compose_data.get("networks", {})
        scripts = []
        for key, config in networks.items():
            if not config.get("external", False):
                continue
            network_name = config.get("name", key)
            scripts.append(
                f"docker network inspect {network_name} > /dev/null 2>&1 || docker network create -d bridge{network_name}"  # noqa
            )
        return "\n".join(scripts)

    def _get_execute_docker_compose_script(
        self,
        compose_cmd: str,
        compose_options: Mapping[JinjaTemplate, JinjaTemplate],
        compose_flags: Iterable[JinjaTemplate],
        compose_args: Iterable[JinjaTemplate],
        *args: Any,
    ) -> str:
        command_options = dict(compose_options)
        command_options["--file"] = self._compose_file
        options = " ".join(
            [
                f"{self.render_str(key)} {double_quote(self.render_str(val))}"
                for key, val in command_options.items()
                if self.render_str(val) != ""
            ]
        )
        flags = " ".join(
            [
                self.render_str(flag)
                for flag in compose_flags
                if self.render_str(flag) != ""
            ]
        )
        args = " ".join(
            [
                double_quote(self.render_str(arg))
                for arg in compose_args
                if self.render_str(arg) != ""
            ]
        )
        return f"docker compose {options} {compose_cmd} {flags} {args}"
