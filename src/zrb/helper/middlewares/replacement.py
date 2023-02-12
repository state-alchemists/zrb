from typing import Callable, Iterable, Mapping
from typeguard import typechecked
from ...task.base_task import BaseTask
from ..util import (
    to_camel_case, to_pascal_case, to_kebab_case, to_snake_case,
    to_human_readable
)

import os


Replacement = Mapping[str, str]
ReplacementMiddleware = Callable[
    [BaseTask, Replacement],
    Replacement
]


@typechecked
def add_camel_key(
    new_key: str, old_key: str
) -> ReplacementMiddleware:
    def _add_camel_case(
        task: BaseTask, replacement: Replacement
    ) -> Replacement:
        replacement[new_key] = to_camel_case(replacement.get(old_key, ''))
        return replacement
    return _add_camel_case


@typechecked
def add_pascal_key(
    new_key: str, old_key: str
) -> ReplacementMiddleware:
    def _add_pascal_case(
        task: BaseTask, replacement: Replacement
    ) -> Replacement:
        replacement[new_key] = to_pascal_case(replacement.get(old_key, ''))
        return replacement
    return _add_pascal_case


@typechecked
def add_kebab_key(
    new_key: str, old_key: str
) -> ReplacementMiddleware:
    def _add_kebab_case(
        task: BaseTask, replacement: Replacement
    ) -> Replacement:
        replacement[new_key] = to_kebab_case(replacement.get(old_key, ''))
        return replacement
    return _add_kebab_case


@typechecked
def add_snake_key(
    new_key: str, old_key: str
) -> ReplacementMiddleware:
    def _add_snake_case(
        task: BaseTask, replacement: Replacement
    ) -> Replacement:
        replacement[new_key] = to_snake_case(replacement.get(old_key, ''))
        return replacement
    return _add_snake_case


@typechecked
def add_human_readable_key(
    new_key: str, old_key: str
) -> ReplacementMiddleware:
    def _add_human_readable(
        task: BaseTask, replacement: Replacement
    ) -> Replacement:
        replacement[new_key] = to_human_readable(replacement.get(old_key, ''))
        return replacement
    return _add_human_readable


@typechecked
def coalesce(
    key: str, alternative_keys: Iterable[str] = [], default_value: str = '',
) -> ReplacementMiddleware:
    def _coalesce(
        task: BaseTask, replacement: Replacement
    ) -> Replacement:
        if replacement[key] is not None and replacement[key] != '':
            return replacement
        for alt in alternative_keys:
            if replacement[alt] is not None and replacement[alt] != '':
                replacement[key] = replacement[alt]
                return replacement
        replacement[key] = default_value
        return replacement
    return _coalesce


@typechecked
def add_base_name_key(
    new_key: str, old_key: str
) -> ReplacementMiddleware:
    def _add_base_name(
        task: BaseTask, replacement: Replacement
    ) -> Replacement:
        replacement[new_key] = os.path.basename(replacement.get(old_key, ''))
        return replacement
    return _add_base_name
