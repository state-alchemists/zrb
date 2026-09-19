import os
import shutil
from collections.abc import Callable
from typing import Any, Unpack, cast

from zrb.attr.type import StrAttr
from zrb.content_transformer.any_content_transformer import AnyContentTransformer
from zrb.content_transformer.content_transformer import ContentTransformer
from zrb.context.any_context import AnyContext
from zrb.task.base.base_task import BaseTask
from zrb.task.base.params import BaseTaskParams
from zrb.util.attr import get_str_attr
from zrb.util.cli.style import stylize_muted

# The cast target below; keep in sync with ContentTransformer's `transform`.
_ContentTransformerTransform = dict[str, StrAttr] | Callable[[AnyContext, str], Any]
TransformConfig = dict[str, StrAttr] | Callable[[AnyContext, str], str]


class Scaffolder(BaseTask):
    def __init__(
        self,
        name: str,
        *,
        source_path: StrAttr | None = None,
        destination_path: StrAttr | None = None,
        transform_path: TransformConfig | None = None,
        transform_content: (
            list[AnyContentTransformer] | AnyContentTransformer | TransformConfig | None
        ) = None,
        **kwargs: Unpack[BaseTaskParams],
    ):
        """Define a task that copies a template tree, rewriting as it goes.

        Args:
            source_path: Directory or file to copy from.
            destination_path: Where to copy to.
            transform_path: How to rewrite copied paths. A mapping of search
                string to replacement, or a callable taking the context and a
                path.
            transform_content: How to rewrite copied file contents. An
                `AnyContentTransformer`, a list of them, a mapping of search
                string to replacement, or a callable taking the context and a
                file path.

        Every parameter `BaseTask` accepts is also accepted here and behaves
        identically; see `BaseTask` for those.
        """
        super().__init__(
            name=name,
            **kwargs,
        )
        self._source_path = source_path
        self._destination_path = destination_path
        self._content_transformers = (
            transform_content if transform_content is not None else []
        )
        self._path_transformer = transform_path if transform_path is not None else {}

    def _get_source_path(self, ctx: AnyContext) -> str:
        return get_str_attr(ctx, self._source_path, "")

    def _get_destination_path(self, ctx: AnyContext) -> str:
        return get_str_attr(ctx, self._destination_path, "")

    def _get_content_transformers(self) -> list[AnyContentTransformer]:
        if callable(self._content_transformers) or isinstance(
            self._content_transformers, dict
        ):
            return cast(
                list[AnyContentTransformer],
                [
                    ContentTransformer(
                        name="default-transform",
                        match=".*",
                        transform=cast(
                            _ContentTransformerTransform,
                            self._content_transformers,
                        ),
                    )
                ],
            )
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
                        ctx.print(stylize_muted(f"{transformer.name}: {file_path}"))
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
            new_file_path = new_file_path.replace(
                keyword, get_str_attr(ctx, replacement, "")
            )
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
