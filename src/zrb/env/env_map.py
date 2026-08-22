import os
from collections.abc import Callable

from zrb.context.any_shared_context import AnySharedContext
from zrb.env.any_env import AnyEnv


class EnvMap(AnyEnv):
    def __init__(
        self,
        vars: dict[str, str] | Callable[[AnySharedContext], dict[str, str]],
        auto_render: bool = True,
        link_to_os: bool = True,
        os_prefix: str | None = None,
    ):
        """Declare several environment variables for a task at once.

        Args:
            vars: The variables by name, or a callable taking the shared context
                and returning them.
            auto_render: Whether to render each value as a template.
            link_to_os: Whether an OS variable of the same name takes precedence.
            os_prefix: Prefix for the OS lookup, so `DEV` reads `DEV_DB_HOST` for
                an entry named `DB_HOST`.
        """
        self._env_map = vars
        self._link_to_os = link_to_os
        self._os_prefix = os_prefix
        self._auto_render = auto_render

    def update_context(self, shared_ctx: AnySharedContext) -> None:
        env_map = self._get_env_map(shared_ctx)
        for name, default_value in env_map.items():
            if self._link_to_os:
                prefix = f"{self._os_prefix}_" if self._os_prefix is not None else ""
                os_name = f"{prefix}{name}"
                value = os.getenv(os_name, default_value)
            else:
                value = default_value
            shared_ctx.env[name] = value

    def _get_env_map(self, shared_ctx: AnySharedContext) -> dict[str, str]:
        if callable(self._env_map):
            return self._env_map(shared_ctx)
        if not self._auto_render:
            return dict(self._env_map)
        return {key: shared_ctx.render(val) for key, val in self._env_map.items()}
