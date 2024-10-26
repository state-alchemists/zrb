from collections.abc import Callable, Mapping
from .any_env import AnyEnv
from ..context.shared_context import SharedContext
import os


class EnvMap(AnyEnv):
    def __init__(
        self,
        vars: Mapping[str, str] | Callable[[SharedContext], Mapping[str, str]],
        auto_render: bool = True,
        link_to_os: bool = True,
        os_prefix: str | None = None,
    ):
        self._env_map = vars
        self._link_to_os = link_to_os
        self._os_prefix = os_prefix
        self._auto_render = auto_render

    def update_shared_context(self, shared_ctx: SharedContext) -> Mapping[str, str]:
        env_map = self._get_env_map(shared_ctx)
        for name, default_value in env_map.items():
            if self._link_to_os:
                prefix = f"{self._os_prefix}_" if self._os_prefix is not None else ""
                os_name = f"{prefix}{name}"
                value = os.getenv(os_name, default_value)
            else:
                value = default_value
            shared_ctx.env[self._name] = value

    def _get_env_map(self, shared_ctx: SharedContext) -> Mapping[str, str]:
        if callable(self._env_map):
            return self._env_map(shared_ctx)
        return {
            key: shared_ctx.render(val)
            for key, val in self._env_map.items()
        }
