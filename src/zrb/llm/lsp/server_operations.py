"""Document-sync and query operations of ``LSPServer`` (its only host)."""

import asyncio
from typing import TYPE_CHECKING, Any

from zrb.context.any_context import zrb_print
from zrb.llm.lsp.configs import detect_language_from_file
from zrb.llm.lsp.protocol import JSONRPCMessage, LSPServerError
from zrb.llm.lsp.symbol_utils import uri_to_path


class LSPServerOperations:
    """Document/query operations for an LSP server."""

    if TYPE_CHECKING:
        # Provided by LSPServer.
        config: Any
        writer: "asyncio.StreamWriter | None"
        initialized: bool
        _diagnostics: dict[str, tuple[int | None, list[dict]]]
        _open_files: set[str]
        _versions: dict[str, int]
        _next_id: Any
        path_to_uri: Any
        _send_request_raw: Any
        _send_notification_raw: Any

    async def goto_definition(
        self, file_path: str, line: int, character: int
    ) -> list[dict] | None:
        """Go to definition for symbol at position."""
        if not self.initialized:
            return None
        await self._ensure_open(file_path)

        request = JSONRPCMessage.create_request(
            "textDocument/definition",
            {
                "textDocument": {"uri": self.path_to_uri(file_path)},
                "position": {"line": line, "character": character},
            },
            self._next_id(),
        )

        result = await self._send_request_raw(request)
        if result is None:
            return None

        if isinstance(result, list):
            return result
        elif isinstance(result, dict) and "uri" in result:
            return [result]
        return None

    async def find_references(
        self,
        file_path: str,
        line: int,
        character: int,
        include_declaration: bool = True,
    ) -> list[dict] | None:
        """Find all references to symbol at position."""
        if not self.initialized:
            return None
        await self._ensure_open(file_path)

        request = JSONRPCMessage.create_request(
            "textDocument/references",
            {
                "textDocument": {"uri": self.path_to_uri(file_path)},
                "position": {"line": line, "character": character},
                "context": {"includeDeclaration": include_declaration},
            },
            self._next_id(),
        )

        result = await self._send_request_raw(request)
        return result if isinstance(result, list) else None

    async def did_open_text_document(self, file_path: str) -> None:
        """Send ``textDocument/didOpen`` with the on-disk contents; idempotent."""
        if not self.initialized:
            return
        uri = self.path_to_uri(file_path)
        if uri in self._open_files:
            return
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                text = f.read()
        except Exception:
            return
        language_id = (
            (self.config.language_ids[0] if self.config.language_ids else None)
            or detect_language_from_file(file_path)
            or "plaintext"
        )
        self._versions[uri] = 1
        notif = JSONRPCMessage.create_notification(
            "textDocument/didOpen",
            {
                "textDocument": {
                    "uri": uri,
                    "languageId": language_id,
                    "version": self._versions[uri],
                    "text": text,
                }
            },
        )
        await self._send_notification_raw(notif)
        self._open_files.add(uri)

    async def did_change_text_document(self, file_path: str) -> None:
        """Send ``textDocument/didChange`` as a full-document replacement.

        Opens the document instead if it was never opened.
        """
        if not self.initialized:
            return
        uri = self.path_to_uri(file_path)
        if uri not in self._open_files:
            await self.did_open_text_document(file_path)
            return
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                text = f.read()
        except Exception:
            return
        self._versions[uri] = self._versions.get(uri, 1) + 1
        notif = JSONRPCMessage.create_notification(
            "textDocument/didChange",
            {
                "textDocument": {"uri": uri, "version": self._versions[uri]},
                "contentChanges": [{"text": text}],
            },
        )
        await self._send_notification_raw(notif)

    async def _ensure_open(self, file_path: str, *, wait_ready: float = 2.0) -> None:
        """Sync ``file_path`` to the server before a query.

        Most servers answer ``textDocument/*`` only for opened documents. On first
        open, wait up to ``wait_ready`` seconds for a ``publishDiagnostics`` as a
        proxy for the initial analysis finishing.
        """
        if not self.initialized or not self.writer:
            return
        uri = self.path_to_uri(file_path)
        first_open = uri not in self._open_files
        if first_open:
            await self.did_open_text_document(file_path)
            # did_open is a no-op when the file can't be read; nothing to wait on.
            if uri not in self._open_files:
                return
        else:
            await self.did_change_text_document(file_path)
        if not first_open or wait_ready <= 0:
            return
        deadline = asyncio.get_event_loop().time() + wait_ready
        while asyncio.get_event_loop().time() < deadline:
            if uri in self._diagnostics:
                return
            await asyncio.sleep(0.05)

    async def get_diagnostics(
        self, file_path: str, *, wait_for_publish: float = 1.5
    ) -> list[dict] | None:
        """Get diagnostics for a file.

        Syncs the file, waits up to ``wait_for_publish`` seconds for a push
        ``publishDiagnostics``, then falls back to LSP 3.17 pull diagnostics.
        """
        if not self.initialized:
            return None

        uri = self.path_to_uri(file_path)
        self._diagnostics.pop(uri, None)

        if uri in self._open_files:
            await self.did_change_text_document(file_path)
        else:
            await self.did_open_text_document(file_path)

        # Read after the sync so a publish for an older version is rejected.
        expected_version = self._versions.get(uri)

        deadline = asyncio.get_event_loop().time() + wait_for_publish
        while True:
            entry = self._diagnostics.get(uri)
            if entry is not None:
                published_version, diagnostics = entry
                if (
                    published_version is None
                    or expected_version is None
                    or published_version >= expected_version
                ):
                    return diagnostics
            if asyncio.get_event_loop().time() >= deadline:
                break
            await asyncio.sleep(0.05)

        request = JSONRPCMessage.create_request(
            "textDocument/diagnostic",
            {"textDocument": {"uri": uri}},
            self._next_id(),
        )
        try:
            result = await self._send_request_raw(request)
            if result and "items" in result:
                return result["items"]
            return result if isinstance(result, list) else None
        except LSPServerError:
            return None

    async def document_symbols(self, file_path: str) -> list[dict] | None:
        """Get all symbols in a document."""
        if not self.initialized:
            return None
        await self._ensure_open(file_path)

        request = JSONRPCMessage.create_request(
            "textDocument/documentSymbol",
            {"textDocument": {"uri": self.path_to_uri(file_path)}},
            self._next_id(),
        )

        result = await self._send_request_raw(request)
        return result if isinstance(result, list) else None

    async def workspace_symbols(self, query: str = "") -> list[dict] | None:
        """Search for symbols across the workspace."""
        if not self.initialized:
            return None

        request = JSONRPCMessage.create_request(
            "workspace/symbol",
            {"query": query},
            self._next_id(),
        )

        result = await self._send_request_raw(request)
        return result if isinstance(result, list) else None

    async def hover(self, file_path: str, line: int, character: int) -> dict | None:
        """Get hover information at position."""
        if not self.initialized:
            return None
        await self._ensure_open(file_path)

        request = JSONRPCMessage.create_request(
            "textDocument/hover",
            {
                "textDocument": {"uri": self.path_to_uri(file_path)},
                "position": {"line": line, "character": character},
            },
            self._next_id(),
        )

        result = await self._send_request_raw(request)
        return result if isinstance(result, dict) else None

    async def rename(
        self,
        file_path: str,
        line: int,
        character: int,
        new_name: str,
        dry_run: bool = True,
    ) -> dict | None:
        """Rename a symbol."""
        if not self.initialized:
            return None
        await self._ensure_open(file_path)

        try:
            prepare_request = JSONRPCMessage.create_request(
                "textDocument/prepareRename",
                {
                    "textDocument": {"uri": self.path_to_uri(file_path)},
                    "position": {"line": line, "character": character},
                },
                self._next_id(),
            )
            prepare_result = await self._send_request_raw(prepare_request)
            if prepare_result is None:
                return None  # Rename not possible at this position
        except LSPServerError:
            pass  # Server doesn't support prepareRename, continue anyway

        request = JSONRPCMessage.create_request(
            "textDocument/rename",
            {
                "textDocument": {"uri": self.path_to_uri(file_path)},
                "position": {"line": line, "character": character},
                "newName": new_name,
            },
            self._next_id(),
        )

        result = await self._send_request_raw(request)
        if result and isinstance(result, dict):
            workspace_edit = result
            if dry_run:
                return workspace_edit
            applied = self._apply_workspace_edit(workspace_edit)
            return {**workspace_edit, "applied": applied}
        return None

    def _apply_workspace_edit(self, workspace_edit: dict) -> bool:
        """Apply an LSP ``WorkspaceEdit`` to disk; True only if every file was written."""
        edits_by_uri = self._collect_text_edits(workspace_edit)
        if not edits_by_uri:
            return False
        success = True
        for uri, edits in edits_by_uri.items():
            if not self._apply_text_edits_to_file(uri, edits):
                success = False
        return success

    @staticmethod
    def _collect_text_edits(workspace_edit: dict) -> dict[str, list[dict]]:
        """Normalize ``changes`` / ``documentChanges`` into {uri: [TextEdit]}."""
        edits_by_uri: dict[str, list[dict]] = {}
        document_changes = workspace_edit.get("documentChanges")
        if isinstance(document_changes, list):
            for doc_edit in document_changes:
                if not isinstance(doc_edit, dict):
                    continue
                uri = (doc_edit.get("textDocument") or {}).get("uri")
                edits = doc_edit.get("edits")
                if uri and isinstance(edits, list):
                    edits_by_uri.setdefault(uri, []).extend(edits)
        changes = workspace_edit.get("changes")
        if isinstance(changes, dict):
            for uri, edits in changes.items():
                if isinstance(edits, list):
                    edits_by_uri.setdefault(uri, []).extend(edits)
        return edits_by_uri

    def _apply_text_edits_to_file(self, uri: str, edits: list[dict]) -> bool:
        """Apply a list of LSP ``TextEdit``s to a single file."""
        path = uri_to_path(uri)
        try:
            with open(path, "r", encoding="utf-8") as f:
                lines = f.read().splitlines(keepends=True)
            offsets = self._line_start_offsets(lines)
            text = "".join(lines)
            # Apply from last edit to first so earlier offsets stay valid.
            for edit in sorted(
                edits,
                key=lambda e: self._range_to_offsets(e["range"], offsets)[0],
                reverse=True,
            ):
                start, end = self._range_to_offsets(edit["range"], offsets)
                text = text[:start] + edit.get("newText", "") + text[end:]
            with open(path, "w", encoding="utf-8") as f:
                f.write(text)
            return True
        except Exception as e:
            zrb_print(f"  LSP rename apply error for {uri}: {e}", plain=True)
            return False

    @staticmethod
    def _line_start_offsets(lines: list[str]) -> list[int]:
        """Character offset at the start of each line (plus a trailing entry)."""
        offsets = [0]
        for line in lines:
            offsets.append(offsets[-1] + len(line))
        return offsets

    @staticmethod
    def _range_to_offsets(rng: dict, offsets: list[int]) -> tuple[int, int]:
        """Convert an LSP ``Range`` to (start, end) character offsets."""

        def pos_to_offset(pos: dict) -> int:
            line = pos.get("line", 0)
            character = pos.get("character", 0)
            base = offsets[min(line, len(offsets) - 1)]
            return base + character

        return pos_to_offset(rng["start"]), pos_to_offset(rng["end"])
