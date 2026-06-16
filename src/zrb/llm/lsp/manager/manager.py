"""Singleton manager that owns running LSP server processes.

Composition: lifecycle (start/stop, project-root detection) and queries
(definition, references, diagnostics, …) live in sibling mixins. The
class itself owns the singleton instance and the per-key cache state.
"""

from __future__ import annotations

import asyncio
import atexit

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

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._servers = {}
            cls._instance._lock = None  # Initialize lazily
            cls._instance._project_roots = {}
        return cls._instance


# Singleton instance
lsp_manager = LSPManager()

# Backstop: a chat/agent run that used LSP tools starts language-server
# subprocesses that nothing else tears down at process exit. At interpreter
# shutdown the owning event loop may already be closed, so the async
# ``shutdown_all`` can no longer run — force-kill survivors synchronously so
# they can't be orphaned or hold the process open. No-op when no servers run.
atexit.register(lsp_manager.force_kill_all)
