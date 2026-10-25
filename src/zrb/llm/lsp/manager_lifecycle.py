"""Server lifecycle for `LSPManager`: start, shut down, project-root detection."""

from __future__ import annotations

import asyncio
from pathlib import Path

from zrb.cmd.command import kill_pid
from zrb.config.config import CFG
from zrb.llm.lsp.server import (
    LSPServer,
    detect_available_lsp_servers,
    get_lsp_config_for_file,
)

# The cache only saves a directory walk, so a FIFO size cap is enough.
_MAX_PROJECT_ROOT_CACHE = 4096

PROJECT_MARKERS = [
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


class LSPManagerLifecycle:
    """Server lifecycle part of `LSPManager`; one server per `(language, root_path)`."""

    def __init__(self) -> None:
        self._servers: dict[str, LSPServer] = {}  # key: "language:root_path"
        self._lock: asyncio.Lock | None = None
        self._project_roots: dict[str, str] = {}  # file_path -> detected root

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

        root = self.detect_project_marker_root(file_path)
        if root is None:
            root = str(_owning_directory(file_path))

        return self._cache_project_root(file_path, root)

    def detect_project_marker_root(self, file_path: str) -> str | None:
        """The nearest ancestor of `file_path` holding a `PROJECT_MARKERS` entry, or None.

        No fallback and no cache: a caller that must tell "inside a project" from
        "loose on disk" needs the absence kept, which `detect_project_root`
        deliberately hides.
        """
        current = _owning_directory(file_path)
        while current != current.parent:
            if any(_has_project_marker(current, marker) for marker in PROJECT_MARKERS):
                return str(current)
            current = current.parent

        return None

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

        `preferred_servers` defaults to `CFG.LLM_LSP_PREFERRED_SERVERS`.
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
            for server in list(self._servers.values()):
                try:
                    await server.stop()
                except Exception as e:
                    CFG.LOGGER.debug(f"LSP server stop failed during shutdown: {e}")
            self._servers.clear()
            self._project_roots.clear()

    def force_kill_all(self) -> None:
        """Synchronously SIGKILL any running LSP server processes; never raises.

        Loop-free, for ``atexit``: the loop owning the transports may be closed.
        """
        for server in list(self._servers.values()):
            process = getattr(server, "process", None)
            if process is None or process.returncode is not None:
                continue
            try:
                # os.kill(pid, SIGKILL) raises ValueError on Windows; kill_pid
                # is psutil-based and works on both.
                kill_pid(process.pid, print_method=CFG.LOGGER.debug)
            except Exception:  # noqa: BLE001 - atexit backstop, must never raise
                pass
        self._servers.clear()


def _owning_directory(file_path: str) -> Path:
    """The resolved directory a walk-up starts from: the file's own, or the path itself."""
    path = Path(file_path).resolve()
    if path.is_file():
        return path.parent
    return path


def _has_project_marker(directory: Path, marker: str) -> bool:
    """Whether `directory` holds an entry named by `marker` (`*.csproj` matches by glob)."""
    if marker.startswith("*"):
        return any(directory.glob(marker))
    return (directory / marker).exists()
