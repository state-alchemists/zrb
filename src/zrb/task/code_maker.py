from typing import Any, List, Mapping, Optional
from typeguard import typechecked
from .base_task import BaseTask
from ..task_env.env import Env
from ..task_group.group import Group
from ..task_input.base_input import BaseInput
from ..helper.file.copy_tree import copy_tree


@typechecked
class CodeMaker(BaseTask):

    def __init__(
        self,
        name: str,
        template_path: str,
        destination_path: str,
        replacements: Mapping[str, str] = {},
        excludes: List[str] = [],
        group: Optional[Group] = None,
        inputs: List[BaseInput] = [],
        envs: List[Env] = [],
        icon: Optional[str] = None,
        color: Optional[str] = None,
        description: str = '',
        upstreams: List[BaseTask] = [],
    ):
        BaseTask.__init__(
            self,
            name=name,
            group=group,
            inputs=inputs,
            envs=envs,
            icon=icon,
            color=color,
            description=description,
            upstreams=upstreams,
            checkers=[],
            checking_interval=0.1,
            retry=0,
            retry_interval=0
        )
        self.template_path = template_path
        self.destination_path = destination_path
        self.replacements = replacements
        self.excudeds = excludes

    async def run(self, **kwargs: Any):
        copy_tree(
            src=self.template_path,
            dst=self.destination_path,
            replacements=self.replacements,
            excludes=self.excudeds
        )