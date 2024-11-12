from dotenv import dotenv_values

from zrb.attr.type import StrAttr
from zrb.context.shared_context import SharedContext
from zrb.env.env_map import EnvMap
from zrb.util.attr import get_str_attr


class EnvFile(EnvMap):
    def __init__(
        self,
        path: StrAttr,
        auto_render: bool = True,
        link_to_os: bool = True,
        os_prefix: str | None = None,
    ):
        super().__init__(
            vars={}, auto_render=auto_render, link_to_os=link_to_os, os_prefix=os_prefix
        )
        self._file_path = path

    def _get_env_map(self, shared_ctx: SharedContext) -> dict[str, str]:
        file_path = get_str_attr(shared_ctx, self._file_path, ".env", self._auto_render)
        return dotenv_values(file_path)
