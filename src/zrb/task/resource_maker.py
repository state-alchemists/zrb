from typing import Any, Callable, List, Mapping, Optional
from typeguard import typechecked
from .base_task import BaseTask
from ..task_env.env import Env
from ..task_group.group import Group
from ..task_input.base_input import BaseInput
from ..helper.file.copy_tree import copy_tree

import os


@typechecked
class ResourceMaker(BaseTask):

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
        scaffold_locks: List[str] = []
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
        self.excludes = excludes
        self.replacements = replacements
        self.scaffold_locks = scaffold_locks

    def create_main_loop(
        self, env_prefix: str = '', raise_error: bool = True
    ) -> Callable[..., bool]:
        return super().create_main_loop(env_prefix, raise_error)

    async def run(self, *args: Any, **kwargs: Any) -> bool:
        # render parameters
        template_path = self.render_str(self.template_path)
        destination_path = self.render_str(self.destination_path)
        excludes = [
            self.render_str(exclude)
            for exclude in self.excludes
        ]
        replacements: Mapping[str, str] = {
            old: self.render_str(new)
            for old, new in self.replacements.items()
        }
        # check scaffold locks
        for scaffold_lock in self.scaffold_locks:
            rendered_scaffold_lock = self.render_str(scaffold_lock)
            if not os.path.exists(rendered_scaffold_lock):
                continue
            raise Exception(' '.join([
                'Operation cancelled since resource already exists:',
                f'{rendered_scaffold_lock},',
            ]))
        self.print_out('\n'.join([
            f'Create resource: {destination_path}',
            f'Template: {template_path}',
            f'Replacements: {replacements}',
            f'Excludes: {excludes}',
        ]))
        copy_tree(
            src=template_path,
            dst=destination_path,
            replacements=replacements,
            excludes=excludes
        )
        return True
