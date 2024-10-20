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

    def update_session(self, session: Session) -> Mapping[str, str]:
        # Update session using file_path
        file_path = self._get_file_path()
        if file_path is not None:
            file_env_map = dotenv_values(self._file_path)
            for var_name, value in file_env_map.items():
                self._update_single_env_session(session, var_name, value)
        # Update session using env_vars
        env_vars_map = self._env_vars if self._env_vars is not None else {}
        for var_name, value in env_vars_map.items():
            value = value(session) if callable(value) else value
            self._update_single_env_session(session, var_name, value)

    def _get_file_path(self, session: Session) -> str:
        if self._file_path is None:
            return None
        if self._auto_render:
            return session.render(self._file_path)
        return self._file_path

    def _update_single_env_session(self, session: Session, var_name: str, value: str):
        if self._use_os_environ:
            os_var_name = self._get_prefixed_var_name(var_name)
            if os_var_name in os.environ:
                session.envs[var_name] = os.environ.get(os_var_name)
                return
        session.envs[var_name] = value

    def _get_prefixed_var_name(self, name: str) -> str:
        if self._os_var_prefix is None:
            return name
        return f"{self._os_var_prefix}_{name}"
