from collections.abc import Callable
from .any_task import AnyTask
from .base_task import BaseTask
from ..attr.type import BoolAttr, StrAttr
from ..env.any_env import AnyEnv
from ..input.any_input import AnyInput
from ..context.any_context import AnyContext
from ..transformer.any_transformer import AnyTransformer
from ..transformer.transformer import Transformer
from ..util.attr import get_str_attr

import os
import shutil

TransformConfig = dict[str, str] | Callable[[AnyContext, str], str]


class Scaffolder(BaseTask):
    def __init__(
        self,
        name: str,
        color: int | None = None,
        icon: str | None = None,
        description: str | None = None,
        cli_only: bool = False,
        input: list[AnyInput] | AnyInput | None = None,
        env: list[AnyEnv] | AnyEnv | None = None,
        source_path: StrAttr | None = None,
        auto_render_source_path: bool = True,
        destination_path: StrAttr | None = None,
        auto_render_destination_path: bool = True,
        rename_path: TransformConfig = {},
        transformer: list[AnyTransformer] | AnyTransformer | TransformConfig = [],
        execute_condition: BoolAttr = True,
        retries: int = 2,
        retry_period: float = 0,
        readiness_check: list[AnyTask] | AnyTask | None = None,
        readiness_check_delay: float = 0.5,
        readiness_check_period: float = 5,
        readiness_failure_threshold: int = 1,
        readiness_timeout: int = 60,
        monitor_readiness: bool = False,
        upstream: list[AnyTask] | AnyTask | None = None,
        fallback: list[AnyTask] | AnyTask | None = None,
    ):
        super().__init__(
            name=name,
            color=color,
            icon=icon,
            description=description,
            cli_only=cli_only,
            input=input,
            env=env,
            execute_condition=execute_condition,
            retries=retries,
            retry_period=retry_period,
            readiness_check=readiness_check,
            readiness_check_delay=readiness_check_delay,
            readiness_check_period=readiness_check_period,
            readiness_failure_threshold=readiness_failure_threshold,
            readiness_timeout=readiness_timeout,
            monitor_readiness=monitor_readiness,
            upstream=upstream,
            fallback=fallback,
        )
        self._source_path = source_path
        self._auto_render_source_path = auto_render_source_path
        self._destination_path = destination_path
        self._auto_render_destination_path = auto_render_destination_path
        self._content_transformers = transformer
        self._path_transformer = rename_path

    def _get_source_path(self, ctx: AnyContext) -> str:
        return get_str_attr(ctx, self._source_path, "", auto_render=True) 

    def _get_destination_path(self, ctx: AnyContext) -> str:
        return get_str_attr(ctx, self._destination_path, "", auto_render=True)

    def _get_content_transformers(self) -> list[AnyTransformer]:
        if callable(self._content_transformers):
            return [Transformer(match="*", transform=self._content_transformers)]
        if isinstance(self._content_transformers, dict):
            return [Transformer(match="*", transform=self._content_transformers)]
        if isinstance(self._content_transformers, AnyTransformer):
            return [self._content_transformers]
        return self._content_transformers

    async def _exec_action(self, ctx: AnyContext):
        source_path = self._get_source_path(ctx)
        destination_path = self._get_destination_path(ctx)
        self._copy_path(ctx, source_path, destination_path)
        transformers = self._get_content_transformers()
        file_paths = self._get_all_file_paths(destination_path)
        for file_path in file_paths:
            for transformer in transformers:
                if transformer.match(ctx, file_path):
                    transformer.transform_file(ctx, file_path)

    def _copy_path(self, ctx: AnyContext, source_path: str, destination_path: str):
        """
        Copies a directory or file from source_path to destination_path recursively.
        """
        if os.path.isdir(source_path):
            for root, dirs, files in os.walk(source_path):
                rel_root = os.path.relpath(root, source_path)
                dest_dir = os.path.join(destination_path, self._transform_path(ctx, rel_root))
                os.makedirs(dest_dir, exist_ok=True)
                for file_name in files:
                    src_file = os.path.join(root, file_name)
                    dest_file = os.path.join(dest_dir, self._transform_path(ctx, file_name))
                    shutil.copy2(src_file, dest_file)
                    ctx.log_info(f"Copied and renamed {src_file} to {dest_file}")
        else:
            dest_file = os.path.join(
                destination_path, self._transform_path(os.path.basename(ctx, source_path))
            )
            shutil.copy2(source_path, dest_file)
            ctx.log_info(f"Copied and renamed {source_path} to {dest_file}")

    def _transform_path(self, ctx: AnyContext, file_path: str):
        if callable(self._path_transformer):
            return self._path_transformer(ctx, file_path)
        new_file_path = file_path
        for keyword, replacement in self._path_transformer.items():
            new_file_path = new_file_path.replace(keyword, replacement)
        return new_file_path

    def _get_all_file_paths(self, path):
        """
        Returns a list of absolute file paths for all files in the given path, recursively.
        """
        file_paths = []
        for root, _, files in os.walk(path):
            for file in files:
                absolute_path = os.path.abspath(os.path.join(root, file))
                file_paths.append(absolute_path)
        return file_paths
