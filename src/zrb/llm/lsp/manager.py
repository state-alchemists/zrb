"""Singleton manager that owns running LSP server processes."""

from __future__ import annotations

import asyncio
import atexit

from zrb.llm.lsp.configs import lsp_server_configs
from zrb.llm.lsp.manager_lifecycle import LSPManagerLifecycle
from zrb.llm.lsp.manager_query import LSPManagerQuery
from zrb.llm.lsp.server import LSPServer, LSPServerConfig


class LSPManager:
    """Singleton manager for LSP servers: lazily started, one per language per project root."""

    _instance: "LSPManager | None" = None
    _lifecycle: LSPManagerLifecycle
    _query: LSPManagerQuery

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._lifecycle = LSPManagerLifecycle()
            # Query holds the manager (not the lifecycle part) so instance-level
            # patches like `patch.object(manager, "get_server", ...)` reach it.
            cls._instance._query = LSPManagerQuery(cls._instance)
        return cls._instance

    @classmethod
    def reset_singleton(cls) -> None:
        """Drop the cached singleton so the next `LSPManager()` builds a fresh one (tests)."""
        cls._instance = None

    @property
    def lock(self) -> asyncio.Lock:
        """Get or create the asyncio lock (lazy: avoids needing a running loop)."""
        return self._lifecycle.lock

    def list_available_servers(self) -> dict[str, str]:
        """All LSP servers detected on the system. Maps name → executable path."""
        return self._lifecycle.list_available_servers()

    def detect_project_root(self, file_path: str) -> str:
        """Walk up from `file_path` looking for a project marker (`.git`, `pyproject.toml`, …)."""
        return self._lifecycle.detect_project_root(file_path)

    async def get_server(
        self,
        file_path: str,
        preferred_servers: list[str] | None = None,
    ) -> LSPServer | None:
        """Get or lazily start an LSP server for `file_path`. None if unavailable."""
        return await self._lifecycle.get_server(file_path, preferred_servers)

    async def shutdown_all(self):
        """Shutdown all LSP servers and forget cached project roots."""
        await self._lifecycle.shutdown_all()

    def force_kill_all(self) -> None:
        """Synchronously SIGKILL any running LSP server processes (atexit backstop)."""
        self._lifecycle.force_kill_all()

    async def find_definition(
        self, symbol_name: str, file_path: str, symbol_kind: str | None = None
    ) -> dict:
        """Find the definition of a symbol."""
        return await self._query.find_definition(symbol_name, file_path, symbol_kind)

    async def find_references(
        self,
        symbol_name: str,
        file_path: str,
        line: int = 0,
        character: int = 0,
        include_declaration: bool = True,
    ) -> dict:
        """Find references to a symbol."""
        return await self._query.find_references(
            symbol_name, file_path, line, character, include_declaration
        )

    async def get_diagnostics(
        self, file_path: str, severity: str | None = None
    ) -> dict:
        """Get diagnostics (errors/warnings) for a file."""
        return await self._query.get_diagnostics(file_path, severity)

    async def get_document_symbols(self, file_path: str) -> dict:
        """Get all symbols defined in a file."""
        return await self._query.get_document_symbols(file_path)

    async def get_workspace_symbols(self, query: str, file_path: str) -> dict:
        """Search for symbols across the workspace."""
        return await self._query.get_workspace_symbols(query, file_path)

    async def get_hover_info(self, file_path: str, line: int, character: int) -> dict:
        """Get hover info (type, docs) at a position."""
        return await self._query.get_hover_info(file_path, line, character)

    async def rename_symbol(
        self,
        symbol_name: str,
        new_name: str,
        file_path: str,
        line: int = 0,
        character: int = 0,
        dry_run: bool = True,
    ) -> dict:
        """Rename a symbol across the workspace."""
        return await self._query.rename_symbol(
            symbol_name, new_name, file_path, line, character, dry_run
        )

    async def find_symbol_position(
        self, file_path: str, symbol_name: str
    ) -> "tuple[int, int] | None":
        return await self._query.find_symbol_position(file_path, symbol_name)

    def register_lsp_server(self, name: str, config: LSPServerConfig) -> None:
        """Register a user LSP server configuration, e.g. from ``zrb_init.py``::

        from zrb.llm.lsp.configs import LSPServerConfig
        from zrb.llm.lsp.manager import lsp_manager

        lsp_manager.register_lsp_server(
            "my-lang-lsp",
            LSPServerConfig(
                name="my-lang-lsp",
                command=["my-lsp-server", "--stdio"],
                language_ids=["mylang"],
                file_extensions=[".my"],
            ),
        )
        """
        lsp_server_configs.register(name, config)


lsp_manager = LSPManager()

# The owning loop may be closed at exit, so async shutdown_all cannot run.
atexit.register(lsp_manager.force_kill_all)
