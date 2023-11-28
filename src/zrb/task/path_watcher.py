from zrb.helper.typing import (
    Any, Callable, Iterable, Mapping, Optional, Union, TypeVar
)
from zrb.helper.typecheck import typechecked
from zrb.task.checker import Checker
from zrb.task.any_task import AnyTask
from zrb.task.any_task_event_handler import (
    OnTriggered, OnWaiting, OnSkipped, OnStarted, OnReady, OnRetry, OnFailed
)
from zrb.task_env.env import Env
from zrb.task_env.env_file import EnvFile
from zrb.task_group.group import Group
from zrb.task_input.any_input import AnyInput

import glob
import os

TPathWatcher = TypeVar('TPathWatcher', bound='PathWatcher')


@typechecked
class PathWatcher(Checker):

    def __init__(
        self,
        name: str = 'watch-path',
        group: Optional[Group] = None,
        inputs: Iterable[AnyInput] = [],
        envs: Iterable[Env] = [],
        env_files: Iterable[EnvFile] = [],
        icon: Optional[str] = None,
        color: Optional[str] = None,
        description: str = '',
        upstreams: Iterable[AnyTask] = [],
        on_triggered: Optional[OnTriggered] = None,
        on_waiting: Optional[OnWaiting] = None,
        on_skipped: Optional[OnSkipped] = None,
        on_started: Optional[OnStarted] = None,
        on_ready: Optional[OnReady] = None,
        on_retry: Optional[OnRetry] = None,
        on_failed: Optional[OnFailed] = None,
        path: str = '',
        checking_interval: Union[int, float] = 0.1,
        progress_interval: Union[int, float] = 30,
        watch_new_files: bool = True,
        watch_modified_files: bool = True,
        watch_deleted_files: bool = True,
        should_execute: Union[bool, str, Callable[..., bool]] = True
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
            should_execute=should_execute,
        )
        self._path = path
        self._watch_new_files = watch_new_files
        self._watch_modified_files = watch_modified_files
        self._watch_deleted_files = watch_deleted_files
        self._rendered_path: str = ''
        self._init_times: Mapping[str, float] = {}

    def copy(self) -> TPathWatcher:
        return super().copy()

    def to_function(
        self,
        env_prefix: str = '',
        raise_error: bool = True,
        is_async: bool = False,
        show_done_info: bool = True
    ) -> Callable[..., bool]:
        return super().to_function(
            env_prefix, raise_error, is_async, show_done_info
        )

    async def run(self, *args: Any, **kwargs: Any) -> bool:
        self._rendered_path = self.render_str(self._path)
        self._init_times = self._get_mod_times()
        return await super().run(*args, **kwargs)

    async def inspect(self, *args: Any, **kwargs: Any) -> bool:
        label = f'Watching {self._rendered_path}'
        try:
            mod_times = self._get_mod_times()
        except Exception:
            self.show_progress(f'{label} Cannot inspect')
        # watch changes
        if self._watch_new_files:
            new_files = mod_times.keys() - self._init_times.keys()
            for file in new_files:
                self.print_out_dark(f'{label} [+] New file detected: {file}')
                return True
        if self._watch_deleted_files:
            deleted_files = self._init_times.keys() - mod_times.keys()
            for file in deleted_files:
                self.print_out_dark(f'{label} [-] File deleted: {file}')
                return True
        if self._watch_modified_files:
            modified_files = {
                file for file, mod_time in mod_times.items()
                if file in mod_times and self._init_times[file] != mod_time
            }
            for file in modified_files:
                self.print_out_dark(f'{label} [/] File modified: {file}')
                return True
        self.show_progress(f'{label} (Nothing changed)')
        return False

    def _get_mod_times(self) -> Mapping[str, float]:
        return {
            file_name: os.stat(file_name).st_mtime
            for file_name in glob.glob(self._rendered_path)
        }

    def __repr__(self) -> str:
        return f'<PathWatcher name={self._name}>'
