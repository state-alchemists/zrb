import socket

from zrb.helper.typecheck import typechecked
from zrb.helper.typing import (
    Any,
    Callable,
    Iterable,
    JinjaTemplate,
    Optional,
    TypeVar,
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
from zrb.task.checker import Checker
from zrb.task_env.env import Env
from zrb.task_env.env_file import EnvFile
from zrb.task_group.group import Group
from zrb.task_input.any_input import AnyInput

TPortChecker = TypeVar("TPortChecker", bound="PortChecker")


@typechecked
class PortConfig:
    def __init__(self, host: str, port: int, timeout: int):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.label = f"Checking {host}:{port}"


@typechecked
class PortChecker(Checker):
    def __init__(
        self,
        name: str = "check-port",
        group: Optional[Group] = None,
        inputs: Iterable[AnyInput] = [],
        envs: Iterable[Env] = [],
        env_files: Iterable[EnvFile] = [],
        icon: Optional[str] = None,
        color: Optional[str] = None,
        description: str = "",
        host: JinjaTemplate = "localhost",
        port: Union[int, JinjaTemplate] = 80,
        timeout: Union[int, JinjaTemplate] = 5,
        upstreams: Iterable[AnyTask] = [],
        on_triggered: Optional[OnTriggered] = None,
        on_waiting: Optional[OnWaiting] = None,
        on_skipped: Optional[OnSkipped] = None,
        on_started: Optional[OnStarted] = None,
        on_ready: Optional[OnReady] = None,
        on_retry: Optional[OnRetry] = None,
        on_failed: Optional[OnFailed] = None,
        checking_interval: Union[int, float] = 0.1,
        progress_interval: Union[int, float] = 5,
        expected_result: bool = True,
        should_execute: Union[bool, str, Callable[..., bool]] = True,
    ):
        Checker.__init__(
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
            checking_interval=checking_interval,
            progress_interval=progress_interval,
            expected_result=expected_result,
            should_execute=should_execute,
        )
        self._host = host
        self._port = port
        self._timeout = timeout
        self._config: Optional[PortChecker] = None

    def copy(self) -> TPortChecker:
        return super().copy()

    def to_function(
        self,
        env_prefix: str = "",
        raise_error: bool = True,
        is_async: bool = False,
        show_done_info: bool = True,
    ) -> Callable[..., bool]:
        return super().to_function(env_prefix, raise_error, is_async, show_done_info)

    async def run(self, *args: Any, **kwargs: Any) -> bool:
        self._config = PortConfig(
            host=self.render_str(self._host),
            port=self.render_int(self._port),
            timeout=self.render_int(self._timeout),
        )
        return await super().run(*args, **kwargs)

    async def inspect(self, *args: Any, **kwargs: Any) -> bool:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(self._config.timeout)
                result = sock.connect_ex((self._config.host, self._config.port))
                if result == 0:
                    self.print_out(f"{self._config.label} (OK)")
                    return True
                self.show_progress(f"{self._config.label} (Not OK)")
        except Exception:
            self.show_progress(f"{self._config.label} (Socker error)")
        return False
