import os

from zrb.context.any_shared_context import AnySharedContext

from ..attr.type import StrAttr
from ..util.attr import get_str_attr
from .any_env import AnyEnv


class Env(AnyEnv):
    def __init__(
        self,
        name: str,
        default: StrAttr,
        auto_render: bool = True,
        link_to_os: bool = True,
        os_name: str | None = None,
    ):
        self._name = name
        self._default = default
        self._auto_render = auto_render
        self._link_to_os = link_to_os
        self._os_name = os_name

    def update_shared_context(self, shared_ctx: AnySharedContext):
        if self._link_to_os:
            os_name = self._name if self._os_name is None else self._os_name
            value = os.getenv(os_name, self._get_default_value(shared_ctx))
        else:
            value = self._get_default_value(shared_ctx)
        shared_ctx.env[self._name] = value

    def _get_default_value(self, shared_ctx: AnySharedContext) -> str:
        return get_str_attr(shared_ctx, self._default, "", self._auto_render)
