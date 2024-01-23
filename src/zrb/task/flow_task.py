from zrb.helper.typecheck import typechecked
from zrb.helper.typing import Callable, Iterable, List, Optional, TypeVar, Union
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
from zrb.task_env.env import Env
from zrb.task_env.env_file import EnvFile
from zrb.task_group.group import Group
from zrb.task_input.any_input import AnyInput

TFlowTask = TypeVar("TFlowTask", bound="FlowTask")


@typechecked
class FlowTask(BaseTask):
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
        upstreams: Iterable[AnyTask] = [],
        on_triggered: Optional[OnTriggered] = None,
        on_waiting: Optional[OnWaiting] = None,
        on_skipped: Optional[OnSkipped] = None,
        on_started: Optional[OnStarted] = None,
        on_ready: Optional[OnReady] = None,
        on_retry: Optional[OnRetry] = None,
        on_failed: Optional[OnFailed] = None,
        checkers: Iterable[AnyTask] = [],
        checking_interval: float = 0,
        retry: int = 2,
        retry_interval: float = 1,
        steps: List[Union[AnyTask, List[AnyTask]]] = [],
        should_execute: Union[bool, str, Callable[..., bool]] = True,
        return_upstream_result: bool = False,
    ):
        final_upstreams: List[AnyTask] = list(upstreams)
        inputs: List[AnyInput] = list(inputs)
        envs: List[Env] = list(envs)
        env_files: List[EnvFile] = list(env_files)
        for step in steps:
            tasks = self._step_to_tasks(step)
            new_upstreams = self._get_embeded_tasks(
                tasks=tasks,
                upstreams=final_upstreams,
                inputs=inputs,
                envs=envs,
                env_files=env_files,
            )
            final_upstreams = new_upstreams
        BaseTask.__init__(
            self,
            name=name,
            group=group,
            inputs=inputs,
            envs=envs,
            env_files=env_files,
            icon=icon,
            color=color,
            description=description,
            upstreams=final_upstreams,
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
            should_execute=should_execute,
            return_upstream_result=return_upstream_result,
            run=lambda *args, **kwargs: kwargs.get("_task").print_out("🆗"),
        )

    def copy(self) -> TFlowTask:
        return super().copy()

    def _step_to_tasks(self, node: Union[AnyTask, List[AnyTask]]) -> List[AnyTask]:
        if isinstance(node, AnyTask):
            return [node]
        return node

    def _get_embeded_tasks(
        self,
        tasks: List[AnyTask],
        upstreams: List[AnyTask],
        inputs: List[AnyInput],
        envs: List[Env],
        env_files: List[EnvFile],
    ) -> List[AnyTask]:
        embeded_tasks: List[AnyTask] = []
        for task in tasks:
            embeded_task = task.copy()
            embeded_task_root_upstreams = self._get_root_upstreams(tasks=[embeded_task])
            for embeded_task_root_upstream in embeded_task_root_upstreams:
                embeded_task_root_upstream.add_upstream(*upstreams)
            # embeded_task.add_upstream(*upstreams)
            embeded_task.add_env(*envs)
            embeded_task.add_env_file(*env_files)
            embeded_task.add_input(*inputs)
            embeded_tasks.append(embeded_task)
        return embeded_tasks

    def _get_root_upstreams(self, tasks: List[AnyTask]):
        root_upstreams = []
        for task in tasks:
            upstreams = task._get_upstreams()
            if len(upstreams) == 0:
                root_upstreams.append(task)
                continue
            for upstream in upstreams:
                if len(upstream._get_upstreams()) == 0:
                    root_upstreams.append(upstream)
                    continue
                root_upstreams += self._get_root_upstreams([upstream])
        return root_upstreams
