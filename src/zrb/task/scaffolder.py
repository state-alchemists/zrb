import os
import shutil
from collections.abc import Callable

from zrb.attr.type import BoolAttr, StrAttr
from zrb.content_transformer.any_content_transformer import AnyContentTransformer
from zrb.content_transformer.content_transformer import ContentTransformer
from zrb.context.any_context import AnyContext
from zrb.env.any_env import AnyEnv
from zrb.input.any_input import AnyInput
from zrb.task.any_task import AnyTask
from zrb.task.base_task import BaseTask
from zrb.util.attr import get_str_attr
from zrb.util.cli.style import stylize_faint

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
        render_source_path: bool = True,
        destination_path: StrAttr | None = None,
        render_destination_path: bool = True,
        transform_path: TransformConfig = {},
        render_transform_path: bool = True,
        transform_content: (
            list[AnyContentTransformer] | AnyContentTransformer | TransformConfig
        ) = [],
        render_transform_content: bool = True,
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
        successor: list[AnyTask] | AnyTask | None = None,
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
            successor=successor,
        )
        self._source_path = source_path
        self._render_source_path = render_source_path
        self._destination_path = destination_path
        self._render_destination_path = render_destination_path
        self._content_transformers = transform_content
        self._render_content_transformers = render_transform_content
        self._path_transformer = transform_path
        self._render_path_transformer = render_transform_path

    def _get_source_path(self, ctx: AnyContext) -> str:
        return get_str_attr(ctx, self._source_path, "", auto_render=True)

    def _get_destination_path(self, ctx: AnyContext) -> str:
        return get_str_attr(ctx, self._destination_path, "", auto_render=True)

    def _get_content_transformers(self) -> list[AnyContentTransformer]:
        if callable(self._content_transformers) or isinstance(
            self._content_transformers, dict
        ):
            return [
                ContentTransformer(
                    name="default-transform",
                    match=".*",
                    transform=self._content_transformers,
                    auto_render=self._render_content_transformers,
                )
            ]
        if isinstance(self._content_transformers, AnyContentTransformer):
            return [self._content_transformers]
        return self._content_transformers

    async def _exec_action(self, ctx: AnyContext):
        source_path = self._get_source_path(ctx)
        destination_path = self._get_destination_path(ctx)
        self._copy_path(ctx, source_path, destination_path)
        transformers = self._get_content_transformers()
        file_path_list = self._get_all_file_paths(destination_path)
        for file_path in file_path_list:
            for transformer in transformers:
                if transformer.match(ctx, file_path):
                    try:
                        ctx.print(stylize_faint(f"{transformer.name}: {file_path}"))
                        transformer.transform_file(ctx, file_path)
                    except UnicodeDecodeError:
                        pass

    def _copy_path(self, ctx: AnyContext, source_path: str, destination_path: str):
        """
        Copies a directory or file from source_path to destination_path recursively.
        """
        if os.path.isdir(source_path):
            for root, dirs, files in os.walk(source_path):
                rel_root = os.path.relpath(root, source_path)
                dest_dir = os.path.join(
                    destination_path, self._transform_path(ctx, rel_root)
                )
                os.makedirs(dest_dir, exist_ok=True)
                for file_name in files:
                    src_file = os.path.join(root, file_name)
                    dest_file = os.path.join(
                        dest_dir, self._transform_path(ctx, file_name)
                    )
                    ctx.log_info(f"Copying {src_file} to {dest_file}")
                    shutil.copy2(src_file, dest_file)
        else:
            ctx.log_info(f"Copying {source_path} to {destination_path}")
            shutil.copy2(source_path, destination_path)

    def _transform_path(self, ctx: AnyContext, file_path: str):
        if callable(self._path_transformer):
            return self._path_transformer(ctx, file_path)
        new_file_path = file_path
        for keyword, replacement in self._path_transformer.items():
            if self._render_path_transformer:
                replacement = ctx.render(replacement)
            new_file_path = new_file_path.replace(keyword, replacement)
        return new_file_path

    def _get_all_file_paths(self, path):
        """
        Returns a list of absolute file paths for all files in the given path, recursively.
        """
        if os.path.isfile(path):
            return [os.path.abspath(path)]
        file_paths = []
        for root, _, files in os.walk(path):
            for file in files:
                absolute_path = os.path.abspath(os.path.join(root, file))
                file_paths.append(absolute_path)
        return file_paths
