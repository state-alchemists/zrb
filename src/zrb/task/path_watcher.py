import os
from collections.abc import Callable, Iterable, Mapping
from typing import Any, Optional, TypeVar, Union

from zrb.helper.accessories.color import colored
from zrb.helper.file.match import get_file_names
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
from zrb.task.watcher import Watcher
from zrb.task_env.env import Env
from zrb.task_env.env_file import EnvFile
from zrb.task_group.group import Group
from zrb.task_input.any_input import AnyInput

logger.debug(colored("Loading zrb.task.path_watcher", attrs=["dark"]))

TPathWatcher = TypeVar("TPathWatcher", bound="PathWatcher")


@typechecked
class PathWatcher(Watcher):
    """
    PathWatcher will wait for any changes specified on  path.

    Once the changes detected, PathWatcher will be completed
    and several xcom will be set:
    - <task-name>.file
    - <task-name>.new-file
    - <task-name>.modified-file
    - <task-name>.deleted-file
    """

    __init_times: Mapping[str, Mapping[str, float]] = {}

    def __init__(
        self,
        name: str = "watch-path",
        group: Optional[Group] = None,
        inputs: Iterable[AnyInput] = [],
        envs: Iterable[Env] = [],
        env_files: Iterable[EnvFile] = [],
        icon: Optional[str] = None,
        color: Optional[str] = None,
        description: str = "",
        upstreams: Iterable[AnyTask] = [],
        fallbacks: Iterable[AnyTask] = [],
        on_triggered: Optional[OnTriggered] = None,
        on_waiting: Optional[OnWaiting] = None,
        on_skipped: Optional[OnSkipped] = None,
        on_started: Optional[OnStarted] = None,
        on_ready: Optional[OnReady] = None,
        on_retry: Optional[OnRetry] = None,
        on_failed: Optional[OnFailed] = None,
        path: JinjaTemplate = "",
        ignored_path: Union[JinjaTemplate, Iterable[JinjaTemplate]] = [],
        checking_interval: Union[int, float] = 0.05,
        progress_interval: Union[int, float] = 30,
        watch_new_files: bool = True,
        watch_modified_files: bool = True,
        watch_deleted_files: bool = True,
        should_execute: Union[bool, JinjaTemplate, Callable[..., bool]] = True,
    ):
        Watcher.__init__(
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
            fallbacks=fallbacks,
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
        self._ignored_path = ignored_path
        self._watch_new_files = watch_new_files
        self._watch_modified_files = watch_modified_files
        self._watch_deleted_files = watch_deleted_files
        self._rendered_path: str = ""
        self._rendered_ignored_paths: list[str] = []

    def copy(self) -> TPathWatcher:
        return super().copy()

    def to_function(
        self,
        env_prefix: str = "",
        raise_error: bool = True,
        is_async: bool = False,
        show_done_info: bool = True,
        should_clear_xcom: bool = False,
        should_stop_looper: bool = False,
    ) -> Callable[..., bool]:
        return super().to_function(
            env_prefix=env_prefix,
            raise_error=raise_error,
            is_async=is_async,
            show_done_info=show_done_info,
            should_clear_xcom=should_clear_xcom,
            should_stop_looper=should_stop_looper,
        )

    async def run(self, *args: Any, **kwargs: Any) -> bool:
        self._rendered_path = self.render_str(self._path)
        self._rendered_ignored_paths = [
            ignored_path
            for ignored_path in self._get_rendered_ignored_paths()
            if ignored_path != ""
        ]
        identifier = self.get_identifier()
        if identifier not in self.__init_times:
            self.__init_times[identifier] = self._get_mod_times()
        return await super().run(*args, **kwargs)

    def _get_rendered_ignored_paths(self) -> list[str]:
        if isinstance(self._ignored_path, str):
            return [self.render_str(self._ignored_path)]
        return [self.render_str(ignored_path) for ignored_path in self._ignored_path]

    def create_loop_inspector(self) -> Callable[..., Optional[bool]]:
        def loop_inspect() -> bool:
            label = f"Watching {self._rendered_path}"
            identifier = self.get_identifier()
            try:
                init_times = self.__init_times[identifier]
                mod_times = self._get_mod_times()
            except Exception as e:
                self.show_progress(f"{label} Cannot inspect")
                raise e
            # watch changes
            if self._watch_new_files:
                new_files = mod_times.keys() - init_times.keys()
                for file in new_files:
                    self.print_out_dark(f"{label} [+] New file detected: {file}")
                    self.set_task_xcom("new-file", file)
                    self.set_task_xcom("file", file)
                    self.__init_times[identifier] = self._get_mod_times()
                    return True
            if self._watch_deleted_files:
                deleted_files = init_times.keys() - mod_times.keys()
                for file in deleted_files:
                    self.print_out_dark(f"{label} [-] File deleted: {file}")
                    self.set_task_xcom("deleted-file", file)
                    self.set_task_xcom("file", file)
                    self.__init_times[identifier] = self._get_mod_times()
                    return True
            if self._watch_modified_files:
                modified_files = {
                    file
                    for file, mod_time in mod_times.items()
                    if file in mod_times and init_times[file] != mod_time
                }
                for file in modified_files:
                    self.print_out_dark(f"{label} [/] File modified: {file}")
                    self.set_task_xcom("modified-file", file)
                    self.set_task_xcom("file", file)
                    self.__init_times[identifier] = self._get_mod_times()
                    return True
            self.show_progress(f"{label} (Nothing changed)")
            return False

        return loop_inspect

    def _get_mod_times(self) -> Mapping[str, float]:
        matches = get_file_names(
            glob_path=self._rendered_path,
            glob_ignored_paths=self._rendered_ignored_paths,
        )
        mod_times: Mapping[str, float] = {}
        for file_name in matches:
            try:
                mod_time = os.stat(file_name).st_mtime
                mod_times[file_name] = mod_time
            except Exception as e:
                self.print_err(e)
        return mod_times
