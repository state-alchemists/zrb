"""Singleton manager that owns running LSP server processes.

Composition: lifecycle (start/stop, project-root detection) and queries
(definition, references, diagnostics, …) live in sibling mixins. The
class itself owns the singleton instance and the per-key cache state.
"""

from __future__ import annotations

import asyncio

from zrb.llm.lsp.manager.lifecycle_mixin import LifecycleMixin
from zrb.llm.lsp.manager.query_mixin import QueryMixin
from zrb.llm.lsp.server import LSPServer


class LSPManager(LifecycleMixin, QueryMixin):
    """
    Singleton manager for LSP server instances.

    Features:
    - Lazy start (only start server when needed)
    - Auto-detect available LSP servers
    - One server instance per language per project root
    - Idle shutdown to free resources
    - Symbol-based API (more LLM-friendly than position-based)
    """

    _instance: "LSPManager | None" = None
    _servers: dict[str, LSPServer]  # key: "language:root_path"
    _lock: asyncio.Lock | None
    _project_roots: dict[str, str]  # file_path -> detected root
    _idle_tasks: dict[str, asyncio.Task]

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._servers = {}
            cls._instance._lock = None  # Initialize lazily
            cls._instance._project_roots = {}
            cls._instance._idle_tasks = {}
        return cls._instance


# Singleton instance
lsp_manager = LSPManager()
