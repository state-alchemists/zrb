"""Server lifecycle for `LSPManager`: start, shut down, project-root detection.

Tracks one server instance per `(language, root_path)` pair. The lock and
the per-key cache live on `LSPManager` itself; this mixin contributes the
methods that read/mutate them.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from zrb.llm.lsp.server import (
    LSPServer,
    detect_available_lsp_servers,
    get_lsp_config_for_file,
)

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
                        self._project_roots[file_path] = str(current)
                        return str(current)
                else:
                    if (current / marker).exists():
                        self._project_roots[file_path] = str(current)
                        return str(current)
            current = current.parent

        self._project_roots[file_path] = str(path)
        return str(path)

    def _get_server_key(self, language: str, root_path: str) -> str:
        return f"{language}:{root_path}"

    async def get_server(
        self,
        file_path: str,
        preferred_servers: list[str] | None = None,
    ) -> LSPServer | None:
        """Get or lazily start an LSP server for `file_path`. None if unavailable."""
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

    async def shutdown_idle(self):
        """Shutdown servers that have been idle for too long.

        Stub: idle tracking is not yet implemented. Kept as a no-op so callers
        can schedule periodic cleanup without checking for the method.
        """
        return None
