import fnmatch
import os
import re
from collections.abc import Callable

from zrb.content_transformer.any_content_transformer import AnyContentTransformer
from zrb.context.any_context import AnyContext
from zrb.util.file import read_file, write_file


class ContentTransformer(AnyContentTransformer):
    def __init__(
        self,
        name: str,
        match: list[str] | str | Callable[[AnyContext, str], bool],
        transform: (
            dict[str, str | Callable[[AnyContext], str]]
            | Callable[[AnyContext, str], None]
        ),
        auto_render: bool = True,
    ):
        self._name = name
        self._match = match
        self._transform_file = transform
        self._auto_render = auto_render

    @property
    def name(self) -> str:
        return self._name

    def match(self, ctx: AnyContext, file_path: str) -> bool:
        if callable(self._match):
            return self._match(ctx, file_path)
        if isinstance(self._match, str):
            patterns = [self._match]
        else:
            patterns = self._match
        for pattern in patterns:
            try:
                if re.fullmatch(pattern, file_path):
                    return True
            except re.error:
                pass
            if os.sep not in pattern and (
                os.altsep is None or os.altsep not in pattern
            ):
                # Pattern like "*.txt" – match only the basename.
                return fnmatch.fnmatch(file_path, os.path.basename(file_path))
            return fnmatch.fnmatch(file_path, file_path)

    def transform_file(self, ctx: AnyContext, file_path: str):
        if callable(self._transform_file):
            return self._transform_file(ctx, file_path)
        transform_map = {
            keyword: self._get_str_replacement(ctx, replacement)
            for keyword, replacement in self._transform_file.items()
        }
        content = read_file(file_path)
        for keyword, replacement in transform_map.items():
            content = content.replace(keyword, replacement)
        write_file(file_path, content)

    def _get_str_replacement(
        self, ctx: AnyContext, replacement: str | Callable[[AnyContext], str]
    ) -> str:
        if callable(replacement):
            return replacement(ctx)
        if self._auto_render:
            return ctx.render(replacement)
        return replacement
