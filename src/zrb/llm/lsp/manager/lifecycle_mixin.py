"""Server lifecycle for `LSPManager`: start, shut down, project-root detection.

Tracks one server instance per `(language, root_path)` pair. The lock and
the per-key cache live on `LSPManager` itself; this mixin contributes the
methods that read/mutate them.
"""

from __future__ import annotations

import asyncio
import os
import signal
from pathlib import Path
from typing import TYPE_CHECKING

from zrb.config.config import CFG
from zrb.llm.lsp.server import (
    LSPServer,
    detect_available_lsp_servers,
    get_lsp_config_for_file,
)

# Bound on the per-file project-root cache. The cache only saves a directory
# walk, so a plain size cap (drop oldest insertion) is enough — precision
# doesn't matter, unboundedness does.
_MAX_PROJECT_ROOT_CACHE = 4096

_PROJECT_MARKERS = [
    ".git",
    "pyproject.toml",
    "setup.py",
    "setup.cfg",
    "requirements.txt",
    "go.mod",
    "Cargo.toml",
    "package.json",
    "build.gradle",
    "pom.xml",
    "Gemfile",
    "composer.json",
    "*.csproj",
    "Makefile",
    "CMakeLists.txt",
]


class LifecycleMixin:
    """Server lifecycle methods for `LSPManager`."""

    # Host-class contract: these attributes are owned by `LSPManager` (see
    # the class-level declarations and `__new__` there). Declared here so
    # static type checkers can verify accesses; the block does not run at runtime.
    if TYPE_CHECKING:
        _lock: asyncio.Lock | None
        _servers: dict[str, LSPServer]
        _project_roots: dict[str, str]

    @property
    def lock(self) -> asyncio.Lock:
        """Get or create the asyncio lock (lazy: avoids needing a running loop)."""
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock

    def list_available_servers(self) -> dict[str, str]:
        """All LSP servers detected on the system. Maps name → executable path."""
        return detect_available_lsp_servers()

    def detect_project_root(self, file_path: str) -> str:
        """Walk up from `file_path` looking for a project marker (`.git`, `pyproject.toml`, …).

        Falls back to the file's directory when nothing is found. Cached per file.
        """
        if file_path in self._project_roots:
            return self._project_roots[file_path]

        path = Path(file_path).resolve()
        if path.is_file():
            path = path.parent

        current = path
        while current != current.parent:
            for marker in _PROJECT_MARKERS:
                if marker.startswith("*"):
                    if list(current.glob(marker)):
                        return self._cache_project_root(file_path, str(current))
                else:
                    if (current / marker).exists():
                        return self._cache_project_root(file_path, str(current))
            current = current.parent

        return self._cache_project_root(file_path, str(path))

    def _cache_project_root(self, file_path: str, root: str) -> str:
        """Cache `file_path → root`, dropping the oldest entry at the bound."""
        if len(self._project_roots) >= _MAX_PROJECT_ROOT_CACHE:
            self._project_roots.pop(next(iter(self._project_roots)))
        self._project_roots[file_path] = root
        return root

    def _get_server_key(self, language: str, root_path: str) -> str:
        return f"{language}:{root_path}"

    async def get_server(
        self,
        file_path: str,
        preferred_servers: list[str] | None = None,
    ) -> LSPServer | None:
        """Get or lazily start an LSP server for `file_path`. None if unavailable.

        When `preferred_servers` is not given, fall back to the configured
        `CFG.LLM_LSP_PREFERRED_SERVERS` so the agent path (whose LSP tools call this
        without an explicit list) honors the user's preference.
        """
        if preferred_servers is None:
            preferred_servers = CFG.LLM_LSP_PREFERRED_SERVERS or None
        config = get_lsp_config_for_file(file_path, preferred_servers)
        if config is None:
            return None

        root = self.detect_project_root(file_path)
        key = self._get_server_key(config.language_ids[0], root)

        async with self.lock:
            if key in self._servers:
                server = self._servers[key]
                if server.is_alive:
                    return server
                del self._servers[key]

            server = LSPServer(config, root)
            success = await server.start()
            if success:
                self._servers[key] = server
                return server
            return None

    async def shutdown_all(self):
        """Shutdown all LSP servers and forget cached project roots."""
        async with self.lock:
            for _key, server in list(self._servers.items()):
                try:
                    await server.stop()
                except Exception:
                    pass
            self._servers.clear()
            self._project_roots.clear()

    def force_kill_all(self) -> None:
        """Synchronously SIGKILL any running LSP server processes.

        A loop-free backstop for interpreter shutdown (``atexit``): by then the
        event loop that owns the subprocess transports may already be closed, so
        the async ``shutdown_all`` can no longer run and ``Process.terminate()``
        would fail. ``os.kill`` on the pid is loop-independent. Best-effort —
        never raises — so it is safe to register as an ``atexit`` handler.
        """
        for server in list(self._servers.values()):
            process = getattr(server, "process", None)
            if process is None or process.returncode is not None:
                continue
            try:
                os.kill(process.pid, signal.SIGKILL)
            except (ProcessLookupError, PermissionError, OSError):
                pass
        self._servers.clear()
