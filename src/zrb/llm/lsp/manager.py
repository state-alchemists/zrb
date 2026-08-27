"""Singleton manager that owns running LSP server processes.

Composition: lifecycle (start/stop, project-root detection) and queries
(definition, references, diagnostics, …) live in composed collaborators,
`self._lifecycle` and `self._query`. This class owns the singleton instance
and re-exposes both collaborators' public methods.
"""

from __future__ import annotations

import asyncio
import atexit

from zrb.llm.lsp.manager_lifecycle import LSPManagerLifecycle
from zrb.llm.lsp.manager_query import LSPManagerQuery
from zrb.llm.lsp.server import LSPServer, LSPServerConfig


class LSPManager:
    """
    Singleton manager for LSP server instances.

    Features:
    - Lazy start (only start server when needed)
    - Auto-detect available LSP servers
    - One server instance per language per project root
    - Symbol-based API (more LLM-friendly than position-based)
    - ``register_lsp_server()`` for user-extensible configs
    """

    _instance: "LSPManager | None" = None
    _lifecycle: LSPManagerLifecycle
    _query: LSPManagerQuery

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._lifecycle = LSPManagerLifecycle()
            # Query keeps the manager reference (not the lifecycle collaborator
            # directly)
            # so instance-level patches like `patch.object(manager, "get_server", ...)`
            # take effect inside Query's own methods too.
            cls._instance._query = LSPManagerQuery(cls._instance)
        return cls._instance

    @classmethod
    def reset_singleton(cls) -> None:
        """Drop the cached singleton so the next `LSPManager()` call builds a
        fresh instance. Test-isolation seam — production code never needs
        more than one manager for the process lifetime."""
        cls._instance = None

    # --- Lifecycle delegators ----------------------------------------------

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

    # --- Query delegators ----------------------------------------------------

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
        """Register a user LSP server configuration.

        Users call this from ``zrb_init.py`` to add support for languages
        not in the built-in table::

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

        Args:
            name: Unique key for this server (used for lookups / preferred lists)
            config: The server configuration
        """
        # lazy: circular — ouroboros at module scope if configs import us back;
        # import here instead, at the first call site (always runtime, never
        # module-load), by which point all modules are fully loaded.
        from zrb.llm.lsp.configs import lsp_server_configs

        lsp_server_configs.register(name, config)


lsp_manager = LSPManager()

# Backstop: a chat/agent run that used LSP tools starts language-server
# subprocesses that nothing else tears down at process exit. At interpreter
# shutdown the owning event loop may already be closed, so the async
# ``shutdown_all`` can no longer run — force-kill survivors synchronously so
# they can't be orphaned or hold the process open. No-op when no servers run.
atexit.register(lsp_manager.force_kill_all)
