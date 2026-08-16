import fnmatch
import os
import re
from collections.abc import Callable
from typing import Any, Literal

from zrb.content_transformer.any_content_transformer import AnyContentTransformer
from zrb.context.any_context import AnyContext
from zrb.util.file import read_file, write_file

MatchMode = Literal["auto", "glob", "regex"]


class ContentTransformer(AnyContentTransformer):
    def __init__(
        self,
        name: str,
        match: list[str] | str | Callable[[AnyContext, str], bool],
        transform: (
            dict[str, str | Callable[[AnyContext], str]]
            | Callable[[AnyContext, str], Any]
        ),
        auto_render: bool = True,
        match_mode: MatchMode = "auto",
    ):
        """Define how matching files are rewritten during scaffolding.

        Args:
            name: Transformer name, used in logs.
            match: Which files this applies to. A glob, a list of globs, or a
                predicate taking the context and a file path.
            transform: The rewrite. Either a mapping of search string to
                replacement (values may be templates or callables), or a callable
                taking the context and a file path that edits the file itself.
            auto_render: Whether to render template values in `transform`.
            match_mode: How string pattern(s) in `match` are interpreted.
                `"auto"` (default) tries each pattern as a regex first, falling
                back to a glob when the pattern isn't valid regex or doesn't
                match as one — this means a glob-shaped pattern that also
                happens to parse as valid regex is matched with regex
                semantics, e.g. `"config.json"` also matches `"configXjson"`
                because `.` is a regex wildcard. Pass `"glob"` to skip the
                regex attempt entirely (only `fnmatch` semantics), or
                `"regex"` to skip the glob fallback entirely (only
                `re.fullmatch` semantics). Ignored when `match` is callable.
        """
        self._name = name
        self._match = match
        self._transform_file = transform
        self._auto_render = auto_render
        self._match_mode: MatchMode = match_mode

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
            if self._match_mode != "glob":
                try:
                    if re.fullmatch(pattern, file_path):
                        return True
                except re.error:
                    pass
            if self._match_mode == "regex":
                continue
            if os.sep not in pattern and (
                os.altsep is None or os.altsep not in pattern
            ):
                # Pattern like "*.txt" – match against the basename only.
                if fnmatch.fnmatch(os.path.basename(file_path), pattern):
                    return True
            elif fnmatch.fnmatch(file_path, pattern):
                # Pattern carries a path separator – match the full path.
                return True
        return False

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
