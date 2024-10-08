from collections.abc import Callable, Iterable, Mapping
from typing import Any, Optional, TypeVar, Union

from zrb.helper.accessories.color import colored
from zrb.helper.file.copy_tree import copy_tree
from zrb.helper.log import logger
from zrb.helper.typecheck import typechecked
from zrb.helper.typing import JinjaTemplate
from zrb.helper.util import (
    to_camel_case,
    to_capitalized_human_readable,
    to_human_readable,
    to_kebab_case,
    to_pascal_case,
    to_snake_case,
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
from zrb.task.base_task.base_task import BaseTask
from zrb.task_env.env import Env
from zrb.task_env.env_file import EnvFile
from zrb.task_group.group import Group
from zrb.task_input.any_input import AnyInput

logger.debug(colored("Loading zrb.task.resource_maker", attrs=["dark"]))

Replacement = Mapping[str, JinjaTemplate]
ReplacementMutator = Callable[[AnyTask, Replacement], Replacement]
TResourceMaker = TypeVar("TResourceMaker", bound="ResourceMaker")


def get_default_resource_skip_parsing() -> list[str]:
    return [
        "*.mp3",
        "*.pdf",
        "*.exe",
        "*.dll",
        "*.bin",
        "*.iso",
        "*.png",
        "*.jpg",
        "*.gif",
        "*.ico",
        "*.pyc",
        "*.gz",
        "*.whl",
        "*.db",
    ]


def get_default_resource_excludes() -> list[str]:
    return [
        "*/.git",
        "*/__pycache__",
        "*/node_modules",
        "*/.venv",
        "*/poetry.lock",
        "*/.env",
    ]


@typechecked
class ResourceMaker(BaseTask):
    def __init__(
        self,
        name: str,
        template_path: JinjaTemplate,
        destination_path: JinjaTemplate,
        replacements: Replacement = {},
        replacement_mutator: Optional[ReplacementMutator] = None,
        excludes: Iterable[str] = get_default_resource_excludes(),
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
        should_execute: Union[bool, JinjaTemplate, Callable[..., bool]] = True,
        skip_parsing: Iterable[str] = get_default_resource_skip_parsing(),
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
            fallbacks=fallbacks,
            on_triggered=on_triggered,
            on_waiting=on_waiting,
            on_skipped=on_skipped,
            on_started=on_started,
            on_ready=on_ready,
            on_retry=on_retry,
            on_failed=on_failed,
            checkers=[],
            checking_interval=0.05,
            retry=0,
            retry_interval=0,
            should_execute=should_execute,
        )
        self._template_path = template_path
        self._destination_path = destination_path
        self._excludes = excludes
        self._replacements = replacements
        self._replacement_mutator = replacement_mutator
        self._skip_parsing = skip_parsing

    def copy(self) -> TResourceMaker:
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
        # render parameters
        template_path = self.render_str(self._template_path)
        destination_path = self.render_str(self._destination_path)
        # render excludes
        self.log_debug(f"Render excludes: {self._excludes}")
        excludes = [self.render_str(exclude) for exclude in self._excludes]
        self.log_debug(f"Rendered excludes: {excludes}")
        # render replacements
        self.log_debug(f"Render replacements: {self._replacements}")
        rendered_replacements: Mapping[str, str] = {
            old: self.render_str(new) for old, new in self._replacements.items()
        }
        self.log_debug(f"Rendered replacements: {rendered_replacements}")
        if self._replacement_mutator is not None:
            self.log_debug("Apply replacement mutator")
            rendered_replacements = self._replacement_mutator(
                self, rendered_replacements
            )
        self.log_debug(f"Apply default replacement mutator: {rendered_replacements}")
        rendered_replacements = self._default_mutate_replacements(rendered_replacements)
        self.log_debug(f"Final replacement: {rendered_replacements}")
        self.print_out_dark(f"Template: {template_path}")
        self.print_out_dark(f"Destination: {destination_path}")
        self.print_out_dark(f"Replacements: {rendered_replacements}")
        self.print_out_dark(f"Excludes: {excludes}")
        self.print_out_dark(f"Skip parsing: {self._skip_parsing}")
        await copy_tree(
            src=template_path,
            dst=destination_path,
            replacements=rendered_replacements,
            excludes=excludes,
            skip_parsing=self._skip_parsing,
        )
        return True

    def _default_mutate_replacements(
        self, rendered_replacements: Mapping[str, str]
    ) -> Mapping[str, str]:
        transformations: Mapping[str, Callable[[str], str]] = {
            "Pascal": to_pascal_case,
            "camel": to_camel_case,
            "kebab": to_kebab_case,
            "KEBAB": _to_upper(to_kebab_case),
            "snake": to_snake_case,
            "SNAKE": _to_upper(to_snake_case),
            "human readable": to_human_readable,
            "Human readable": to_capitalized_human_readable,
            "HUMAN READABLE": _to_upper(to_capitalized_human_readable),
        }
        keys = list(rendered_replacements.keys())
        for key in keys:
            value = rendered_replacements[key]
            for prefix, transform in transformations.items():
                prefixed_key = transform(prefix + " " + key)
                if prefixed_key in rendered_replacements:
                    continue
                transformed_value = transform(value)
                rendered_replacements[prefixed_key] = transformed_value
            if key != key.upper():
                rendered_replacements[key.upper()] = value.upper()
        return rendered_replacements


def _to_upper(fn: Callable[[str], str]) -> Callable[[str], str]:
    def upperized_fn(text: str) -> str:
        return fn(text).upper()

    return upperized_fn
