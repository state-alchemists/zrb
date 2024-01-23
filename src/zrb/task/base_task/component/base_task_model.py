import datetime
import logging
import os
import sys
from functools import lru_cache

from zrb.config.config import env_prefix, logging_level, show_time
from zrb.helper.accessories.color import colored
from zrb.helper.log import logger
from zrb.helper.string.conversion import to_variable_name
from zrb.helper.string.modification import double_quote
from zrb.helper.typecheck import typechecked
from zrb.helper.typing import (
    Any,
    Callable,
    Iterable,
    JinjaTemplate,
    List,
    Mapping,
    Optional,
    Union,
)
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
from zrb.task.base_task.component.common_task_model import CommonTaskModel
from zrb.task.base_task.component.pid_model import PidModel
from zrb.task.base_task.component.trackers import TimeTracker
from zrb.task_env.env import Env
from zrb.task_env.env_file import EnvFile
from zrb.task_group.group import Group
from zrb.task_input.any_input import AnyInput

LOG_NAME_LENGTH = 20


@typechecked
class BaseTaskModel(CommonTaskModel, PidModel, TimeTracker):
    def __init__(
        self,
        name: str,
        group: Optional[Group] = None,
        description: str = "",
        inputs: List[AnyInput] = [],
        envs: Iterable[Env] = [],
        env_files: Iterable[EnvFile] = [],
        icon: Optional[str] = None,
        color: Optional[str] = None,
        retry: int = 2,
        retry_interval: Union[int, float] = 1,
        upstreams: Iterable[AnyTask] = [],
        checkers: Iterable[AnyTask] = [],
        checking_interval: Union[int, float] = 0,
        run: Optional[Callable[..., Any]] = None,
        on_triggered: Optional[OnTriggered] = None,
        on_waiting: Optional[OnWaiting] = None,
        on_skipped: Optional[OnSkipped] = None,
        on_started: Optional[OnStarted] = None,
        on_ready: Optional[OnReady] = None,
        on_retry: Optional[OnRetry] = None,
        on_failed: Optional[OnFailed] = None,
        should_execute: Union[bool, JinjaTemplate, Callable[..., bool]] = True,
        return_upstream_result: bool = False,
    ):
        self.__rjust_full_cli_name: Optional[str] = None
        self.__has_cli_interface = False
        self.__complete_name: Optional[str] = None
        CommonTaskModel.__init__(
            self,
            name=name,
            group=group,
            description=description,
            inputs=inputs,
            envs=envs,
            env_files=env_files,
            icon=icon,
            color=color,
            retry=retry,
            retry_interval=retry_interval,
            upstreams=upstreams,
            checkers=checkers,
            checking_interval=checking_interval,
            run=run,
            on_triggered=on_triggered,
            on_waiting=on_waiting,
            on_skipped=on_skipped,
            on_started=on_started,
            on_ready=on_ready,
            on_retry=on_retry,
            on_failed=on_failed,
            should_execute=should_execute,
            return_upstream_result=return_upstream_result,
        )
        PidModel.__init__(self)
        TimeTracker.__init__(self)
        self.__args: List[Any] = []
        self.__kwargs: Mapping[str, Any] = {}

    def _set_args(self, args: Iterable[Any]):
        """
        Set args that will be shown at the end of the execution
        """
        self.__args = list(args)

    def _set_kwargs(self, kwargs: Mapping[str, Any]):
        """
        Set kwargs that will be shown at the end of the execution
        """
        self.__kwargs = kwargs

    def log_debug(self, message: Any):
        if logging_level > logging.DEBUG:
            return
        prefix = self.__get_log_prefix()
        colored_message = colored(f"{prefix} • {message}", attrs=["dark"])
        logger.debug(colored_message)

    def log_warn(self, message: Any):
        if logging_level > logging.WARNING:
            return
        prefix = self.__get_log_prefix()
        colored_message = colored(f"{prefix} • {message}", attrs=["dark"])
        logger.warning(colored_message)

    def log_info(self, message: Any):
        if logging_level > logging.INFO:
            return
        prefix = self.__get_log_prefix()
        colored_message = colored(f"{prefix} • {message}", attrs=["dark"])
        logger.info(colored_message)

    def log_error(self, message: Any):
        if logging_level > logging.ERROR:
            return
        prefix = self.__get_log_prefix()
        colored_message = colored(f"{prefix} • {message}", color="red", attrs=["bold"])
        logger.error(colored_message, exc_info=True)

    def log_critical(self, message: Any):
        if logging_level > logging.CRITICAL:
            return
        prefix = self.__get_log_prefix()
        colored_message = colored(f"{prefix} • {message}", color="red", attrs=["bold"])
        logger.critical(colored_message, exc_info=True)

    def print_out(self, message: Any, trim_message: bool = True):
        prefix = self.__get_colored_print_prefix()
        message_str = f"{message}".rstrip() if trim_message else f"{message}"
        print(f"🤖 ○ {prefix} • {message_str}", file=sys.stderr)
        sys.stderr.flush()

    def print_err(self, message: Any, trim_message: bool = True):
        prefix = self.__get_colored_print_prefix()
        message_str = f"{message}".rstrip() if trim_message else f"{message}"
        print(f"🤖 △ {prefix} • {message_str}", file=sys.stderr)
        sys.stderr.flush()

    def print_out_dark(self, message: Any, trim_message: bool = True):
        message_str = f"{message}"
        self.print_out(colored(message_str, attrs=["dark"]), trim_message)

    def _print_result(self, result: Any):
        if result is None:
            return
        if self._return_upstream_result:
            # if _return_upstream_result, result is list (see: self._run_all)
            upstreams = self._get_upstreams()
            upstream_results = list(result)
            for upstream_index, upstream_result in enumerate(upstream_results):
                upstreams[upstream_index]._print_result(upstream_result)
            return
        self.print_result(result)

    def print_result(self, result: Any):
        print(result)

    def _play_bell(self):
        print("\a", end="", file=sys.stderr, flush=True)

    def _show_done_info(self):
        elapsed_time = self._get_elapsed_time()
        self.print_out_dark(f"Completed in {elapsed_time} seconds")
        self._play_bell()

    def _show_env_prefix(self):
        if env_prefix == "":
            return
        colored_env_prefix = colored(env_prefix, color="yellow")
        colored_label = colored("Your current environment: ", attrs=["dark"])
        print(colored(f"{colored_label}{colored_env_prefix}"), file=sys.stderr)

    def _show_run_command(self):
        if not self.__has_cli_interface:
            return
        params: List[str] = [double_quote(arg) for arg in self.__args]
        for task_input in self._get_combined_inputs():
            if task_input.is_hidden():
                continue
            key = task_input.get_name()
            kwarg_key = to_variable_name(key)
            quoted_value = double_quote(str(self.__kwargs[kwarg_key]))
            params.append(f"--{key} {quoted_value}")
        run_cmd = self._get_full_cli_name()
        run_cmd_with_param = run_cmd
        if len(params) > 0:
            param_str = " ".join(params)
            run_cmd_with_param += " " + param_str
        colored_command = colored(run_cmd_with_param, color="yellow")
        colored_label = colored("To run again: ", attrs=["dark"])
        print(colored(f"{colored_label}{colored_command}"), file=sys.stderr)

    def __get_colored_print_prefix(self) -> str:
        return self.__get_colored(self.__get_print_prefix())

    def __get_colored(self, text: str) -> str:
        return colored(text, color=self.get_color())

    def __get_print_prefix(self) -> str:
        common_prefix = self.__get_common_prefix(show_time=show_time)
        icon = self.get_icon()
        length = LOG_NAME_LENGTH - len(icon)
        rjust_cli_name = self.__get_rjust_full_cli_name(length)
        return f"{common_prefix} {icon} {rjust_cli_name}"

    def __get_log_prefix(self) -> str:
        common_prefix = self.__get_common_prefix(show_time=False)
        icon = self.get_icon()
        length = LOG_NAME_LENGTH - len(icon)
        filled_name = self.__get_rjust_full_cli_name(length)
        return f"{common_prefix} {icon} {filled_name}"

    def __get_common_prefix(self, show_time: bool) -> str:
        attempt = self._get_attempt()
        max_attempt = self._get_max_attempt()
        pid = str(self._get_task_pid()).rjust(6)
        if show_time:
            now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            return f"◷ {now} ❁ {pid} → {attempt}/{max_attempt}"
        return f"❁ {pid} → {attempt}/{max_attempt}"

    @lru_cache
    def __get_rjust_full_cli_name(self, length: int) -> str:
        if self.__rjust_full_cli_name is not None:
            return self.__rjust_full_cli_name
        complete_name = self._get_full_cli_name()
        self.__rjust_full_cli_name = complete_name.rjust(length, " ")
        return self.__rjust_full_cli_name

    @lru_cache
    def __get_executable_name(self) -> str:
        if len(sys.argv) > 0 and sys.argv[0] != "":
            return os.path.basename(sys.argv[0])
        return "zrb"

    @lru_cache
    def _get_full_cli_name(self) -> str:
        if self.__complete_name is not None:
            return self.__complete_name
        executable_prefix = ""
        if self.__has_cli_interface:
            executable_prefix += self.__get_executable_name() + " "
        cli_name = self.get_cli_name()
        if self._group is None:
            self.__complete_name = f"{executable_prefix}{cli_name}"
            return self.__complete_name
        group_cli_name = self._group._get_full_cli_name()
        self.__complete_name = f"{executable_prefix}{group_cli_name} {cli_name}"  # noqa
        return self.__complete_name

    def _set_has_cli_interface(self):
        self.__has_cli_interface = True
