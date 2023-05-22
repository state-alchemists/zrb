from typing import Any, Callable, Iterable, Mapping, Optional
from typeguard import typechecked
from .base_task import BaseTask, Group
from ..task_env.env import Env
from ..task_env.env_file import EnvFile
from ..task_input.base_input import BaseInput
from ..helper.file.copy_tree import copy_tree
from ..helper.util import (
    to_camel_case, to_pascal_case, to_kebab_case, to_snake_case,
    to_human_readable, to_capitalized_human_readable
)

import os

Replacement = Mapping[str, str]
ReplacementMutator = Callable[
    [BaseTask, Replacement],
    Replacement
]


@typechecked
class ResourceMaker(BaseTask):

    def __init__(
        self,
        name: str,
        template_path: str,
        destination_path: str,
        replacements: Replacement = {},
        replacement_mutator: Optional[ReplacementMutator] = None,
        excludes: Iterable[str] = [],
        group: Optional[Group] = None,
        inputs: Iterable[BaseInput] = [],
        envs: Iterable[Env] = [],
        env_files: Iterable[EnvFile] = [],
        icon: Optional[str] = None,
        color: Optional[str] = None,
        description: str = '',
        upstreams: Iterable[BaseTask] = [],
        locks: Iterable[str] = []
    ):
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
        self.replacement_mutator = replacement_mutator
        self.locks = locks

    def create_main_loop(
        self, env_prefix: str = '', raise_error: bool = True
    ) -> Callable[..., bool]:
        return super().create_main_loop(env_prefix, raise_error)

    async def run(self, *args: Any, **kwargs: Any) -> bool:
        # render parameters
        template_path = self.render_str(self.template_path)
        destination_path = self.render_str(self.destination_path)
        # check scaffold locks
        for scaffold_lock in self.locks:
            self.log_debug(f'Render scaaffold lock: {scaffold_lock}')
            rendered_scaffold_lock = self.render_str(scaffold_lock)
            self.log_debug(f'Rendered scaffold lock: {rendered_scaffold_lock}')
            if not os.path.exists(rendered_scaffold_lock):
                continue
            raise Exception(' '.join([
                'Operation cancelled since resource already exists:',
                f'{rendered_scaffold_lock},',
            ]))
        # render excludes
        self.log_debug(f'Render excludes: {self.excludes}')
        excludes = [
            self.render_str(exclude)
            for exclude in self.excludes
        ]
        self.log_debug(f'Rendered excludes: {excludes}')
        self.log_debug(f'Render replacements: {self.replacements}')
        rendered_replacements: Mapping[str, str] = {
            old: self.render_str(new)
            for old, new in self.replacements.items()
        }
        self.log_debug(f'Rendered replacements: {rendered_replacements}')
        if self.replacement_mutator is not None:
            self.log_debug('Apply replacement mutator')
            rendered_replacements = self.replacement_mutator(
                self, rendered_replacements
            )
        self.log_debug(
            f'Apply default replacement mutator: {rendered_replacements}'
        )
        rendered_replacements = self._default_mutate_replacements(
            rendered_replacements
        )
        self.log_debug(f'Final replacement: {rendered_replacements}')
        self.print_out_dark(f'Template: {template_path}')
        self.print_out_dark(f'Destination: {destination_path}')
        self.print_out_dark(f'Replacements: {rendered_replacements}')
        self.print_out_dark(f'Excludes: {excludes}')
        await copy_tree(
            src=template_path,
            dst=destination_path,
            replacements=rendered_replacements,
            excludes=excludes
        )
        return True

    def _default_mutate_replacements(
        self, rendered_replacements: Mapping[str, str]
    ) -> Mapping[str, str]:
        transformations: Mapping[str, Callable[[str], str]] = {
            'Pascal': to_pascal_case,
            'kebab': to_kebab_case,
            'camel': to_camel_case,
            'snake': to_snake_case,
            'human readable': to_human_readable,
            'Human readable': to_capitalized_human_readable,
        }
        keys = list(rendered_replacements.keys())
        for key in keys:
            value = rendered_replacements[key]
            for prefix, transform in transformations.items():
                prefixed_key = transform(prefix + ' ' + key)
                if prefixed_key in rendered_replacements:
                    continue
                transformed_value = transform(value)
                rendered_replacements[prefixed_key] = transformed_value
        return rendered_replacements
