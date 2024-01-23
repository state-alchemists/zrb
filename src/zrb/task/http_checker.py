from http.client import HTTPConnection, HTTPSConnection

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

THTTPChecker = TypeVar("THTTPChecker", bound="HTTPChecker")


@typechecked
class HttpConnectionConfig:
    def __init__(
        self,
        is_https: bool,
        method: str,
        host: str,
        port: int,
        url: str,
        timeout: int,
    ):
        self.is_https = is_https
        self.method = method
        self.host = host
        self.port = port
        self.url = "/" + url if not url.startswith("/") else url
        self.timeout = timeout
        self.protocol = "https" if self.is_https else "http"
        full_url = f"{self.protocol}://{self.host}:{self.port}{self.url}"
        self.label = f"{self.method} {full_url}"

    def get_connection(self) -> Union[HTTPConnection, HTTPSConnection]:
        if self.is_https:
            return HTTPSConnection(host=self.host, port=self.port, timeout=self.timeout)
        return HTTPConnection(host=self.host, port=self.port, timeout=self.timeout)


@typechecked
class HTTPChecker(Checker):
    def __init__(
        self,
        name: str = "check-http",
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
        method: str = "HEAD",
        url: str = "/",
        is_https: Union[bool, str] = False,
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
        should_execute: Union[bool, JinjaTemplate, Callable[..., bool]] = True,
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
        self._method = method
        self._url = url
        self._is_https = is_https
        self._config: Optional[HttpConnectionConfig] = None

    def copy(self) -> THTTPChecker:
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
        self._config = HttpConnectionConfig(
            is_https=self.render_bool(self._is_https),
            method=self.render_str(self._method),
            host=self.render_str(self._host),
            port=self.render_int(self._port),
            url=self.render_str(self._url),
            timeout=self.render_int(self._timeout),
        )
        return await super().run(*args, **kwargs)

    async def inspect(self, *args: Any, **kwargs: Any) -> bool:
        conn = self._config.get_connection()
        try:
            conn.request(self._config.method, self._config.url)
            res = conn.getresponse()
            if res.status < 300:
                self.log_info("Connection success")
                self.print_out(f"{self._config.label} {res.status} (OK)")
                return True
            self.show_progress(f"{self._config.label} {res.status} (Not OK)")
        except Exception:
            self.show_progress(f"{self._config.label} Connection error")
        finally:
            conn.close()
        return False
