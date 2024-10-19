from collections.abc import Callable, Mapping
from dotenv import dotenv_values
from .any_env import AnyEnv
from ..session.session import Session

import os


class Env(AnyEnv):
    def __init__(
        self,
        file_path: str | None = None,
        env_vars: Mapping[str, str | Callable[[Session], str]] | None = None,
        use_os_environ: bool = True,
        os_var_prefix: str | None = None,
        auto_render: bool = True,
    ):
        self._file_path = file_path
        self._env_vars = env_vars
        self._use_os_environ = use_os_environ
        self._os_var_prefix = os_var_prefix
        self._auto_render = auto_render

    def get_env_map(self, session: Session) -> Mapping[str, str]:
        env_map = self._get_env_map(session)
        if not self._use_os_environ:
            return env_map
        for var_name in env_map:
            prefixed_var_name = self._get_prefixed_var_name(var_name)
            if prefixed_var_name in os.environ:
                env_map[var_name] = os.environ.get(prefixed_var_name)

    def _get_prefixed_var_name(self, name: str) -> str:
        if self._os_var_prefix is None:
            return name
        return f"{self._os_var_prefix}_{name}"

    def _get_env_map(self, session: Session) -> Mapping[str, str]:
        """Retrieve the combined environment map."""
        file_env_map = self._load_from_file_path()
        var_env_map = self._load_from_env_vars(session)
        # Merge the two dictionaries, with env_vars overriding file_path values
        combined_env_map = file_env_map.copy()  # Start with file env
        combined_env_map.update(var_env_map)    # Override with env_vars
        return combined_env_map

    def _load_from_file_path(self) -> Mapping[str, str]:
        if self._file_path is None:
            return {}
        return dotenv_values(self._file_path)

    def _load_from_env_vars(self, session: Session) -> Mapping[str, str]:
        if self._env_vars is None:
            return {}
        env_map: Mapping[str, str] = {}
        for key, value in self._env_vars.items():
            if callable(value):
                env_map[key] = value(session)  # Call the function
            else:
                env_map[key] = value  # Direct value
            # render
            if self._auto_render:
                env_map[key] = session.render(env_map[key])
        return env_map
