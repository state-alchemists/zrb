import fnmatch
import re
from collections.abc import Callable

from zrb.content_transformer.any_content_transformer import AnyContentTransformer
from zrb.context.any_context import AnyContext


class ContentTransformer(AnyContentTransformer):

    def __init__(
        self,
        match: list[str] | str | Callable[[AnyContext, str], bool],
        transform: (
            dict[str, str | Callable[[AnyContext], str]]
            | Callable[[AnyContext, str], str]
        ),
        auto_render: bool = True,
    ):
        self._match = match
        self._transform_file = transform
        self._auto_render = auto_render

    def match(self, ctx: AnyContext, file_path: str) -> bool:
        if callable(self._match):
            return self._match(ctx, file_path)
        patterns = [self._match] if isinstance(self._match, str) else self._match
        for pattern in patterns:
            try:
                if re.fullmatch(pattern, file_path):
                    return True
            except re.error:
                pass
            return fnmatch.fnmatch(file_path, pattern)

    def transform_file(self, ctx: AnyContext, file_path: str):
        if callable(self._transform_file):
            return self._transform_file(ctx, file_path)
        transform_map = {
            keyword: self._get_str_replacement(ctx, replacement)
            for keyword, replacement in self._transform_file.items()
        }
        with open(file_path, "r") as f:
            content = f.read()
        for keyword, replacement in transform_map.items():
            content = content.replace(keyword, replacement)
        with open(file_path, "w") as f:
            f.write(content)

    def _get_str_replacement(
        self, ctx: AnyContext, replacement: str | Callable[[AnyContext], str]
    ) -> str:
        if callable(replacement):
            return replacement(ctx)
        if self._auto_render:
            return ctx.render(replacement)
        return replacement
