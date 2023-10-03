from zrb.helper.typing import (
    Callable, Iterable, List, Optional, TypeVar, Union
)
from zrb.helper.typecheck import typechecked
from zrb.task.base_task import BaseTask
from zrb.task.any_task import AnyTask
from zrb.task_env.env import Env
from zrb.task_env.env_file import EnvFile
from zrb.task_group.group import Group
from zrb.task_input.any_input import AnyInput


TFlowTask = TypeVar('TFlowTask', bound='FlowTask')


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
        description: str = '',
        upstreams: Iterable[AnyTask] = [],
        checkers: Iterable[AnyTask] = [],
        checking_interval: float = 0,
        retry: int = 2,
        retry_interval: float = 1,
        steps: List[Union[AnyTask, List[AnyTask]]] = [],
        skip_execution: Union[bool, str, Callable[..., bool]] = False,
        return_upstream_result: bool = False
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
                env_files=env_files
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
            checkers=checkers,
            checking_interval=checking_interval,
            retry=retry,
            retry_interval=retry_interval,
            skip_execution=skip_execution,
            return_upstream_result=return_upstream_result,
            run=lambda *args, **kwargs: kwargs.get('_task').print_out('🆗')
        )

    def copy(self) -> TFlowTask:
        return super().copy()

    def _step_to_tasks(
        self, node: Union[AnyTask, List[AnyTask]]
    ) -> List[AnyTask]:
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
            embeded_task.add_upstreams(*upstreams)
            embeded_task.add_envs(*envs)
            embeded_task.add_env_files(*env_files)
            embeded_task.add_inputs(*inputs)
            embeded_tasks.append(embeded_task)
        return embeded_tasks

    def __repr__(self) -> str:
        return f'<FlowTask name={self._name}>'
