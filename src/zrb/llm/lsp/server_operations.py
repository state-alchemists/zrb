"""
LSP document and query operations.

Mixin holding the document-synchronization and query methods for an LSP
server (definition, references, diagnostics, symbols, hover, rename, and the
workspace-edit application helpers). Mixed into ``LSPServer``; relies on the
host class for transport/state (``self._send_request_raw``, ``self._next_id``,
``self._path_to_uri``, ``self._uri_to_path``, ``self.initialized``, etc.).
"""

import asyncio

from zrb.context.any_context import zrb_print
from zrb.llm.lsp.configs import detect_language_from_file
from zrb.llm.lsp.protocol import JSONRPCMessage, LSPServerError


class OperationsMixin:
    """Document/query operations for an LSP server."""

    # --- LSP API Methods ---

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
                "textDocument": {"uri": self._path_to_uri(file_path)},
                "position": {"line": line, "character": character},
            },
            self._next_id(),
        )

        result = await self._send_request_raw(request)
        if result is None:
            return None

        # Handle both Location and LocationLink
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
                "textDocument": {"uri": self._path_to_uri(file_path)},
                "position": {"line": line, "character": character},
                "context": {"includeDeclaration": include_declaration},
            },
            self._next_id(),
        )

        result = await self._send_request_raw(request)
        return result if isinstance(result, list) else None

    async def did_open_text_document(self, file_path: str) -> None:
        """Send ``textDocument/didOpen`` so the server analyzes this file.

        Idempotent — a no-op if the file is already open in this session.
        Reads the current on-disk contents and sends them along with the
        language id from the server config (falling back to extension-based
        detection). LSP servers won't analyze files they haven't been told
        about, so this is the prerequisite for receiving push diagnostics.
        """
        if not self.initialized:
            return
        uri = self._path_to_uri(file_path)
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
        """Send ``textDocument/didChange`` with the current on-disk contents.

        Uses a full-document replacement (``contentChanges = [{"text": ...}]``)
        rather than incremental edits — simpler, and the canonical source is
        the file on disk anyway. The LSP spec permits a single ``text``-only
        change in both Full and Incremental sync modes, and pylsp / pyright /
        gopls / rust-analyzer all accept it. Servers that declared
        ``textDocumentSync: None`` are not supported here. If the document was
        never opened, delegates to :meth:`did_open_text_document`.
        """
        if not self.initialized:
            return
        uri = self._path_to_uri(file_path)
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
        """Make sure the server has analyzed ``file_path`` before a query.

        Most servers (pyright, gopls, rust-analyzer, …) serve ``textDocument/*``
        requests ONLY for documents opened via ``didOpen`` — a request for an
        unopened file returns null/empty. So every file-scoped query syncs the
        document first (``didOpen`` on first contact, ``didChange`` thereafter).

        On first open we also wait briefly for the server to finish its initial
        analysis, using the first ``publishDiagnostics`` for this URI as a
        readiness proxy (definition/hover/references return empty until analysis
        completes). Bounded by ``wait_ready`` so servers that never publish
        (or files with no diagnostics) don't stall the call.
        """
        if not self.initialized or not self.writer:
            return
        uri = self._path_to_uri(file_path)
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

        Synchronizes the file with the server (``didOpen`` on first contact,
        ``didChange`` on subsequent calls) then waits up to ``wait_for_publish``
        seconds for the resulting ``textDocument/publishDiagnostics`` push
        notification. Falls back to LSP 3.17 pull-diagnostics if no push
        arrived (servers that support pull are happy; the rest just return
        whatever the cache has).
        """
        if not self.initialized:
            return None

        uri = self._path_to_uri(file_path)
        # Drop the cached entry so we can detect the fresh publish.
        self._diagnostics.pop(uri, None)

        if uri in self._open_files:
            await self.did_change_text_document(file_path)
        else:
            await self.did_open_text_document(file_path)

        # Version to gate against: any cached entry from a publish for an
        # older version is stale and should be ignored. Read after the
        # didOpen/didChange call so we see the version we just sent.
        expected_version = self._versions.get(uri)

        # Wait for the server to publish diagnostics. Single-threaded asyncio
        # means _handle_message can only run between our awaits, so poll on
        # short sleeps. 50ms is fine: pylsp/pyright typically publish in
        # 50–500ms after didChange.
        deadline = asyncio.get_event_loop().time() + wait_for_publish
        while True:
            entry = self._diagnostics.get(uri)
            if entry is not None:
                published_version, diagnostics = entry
                # Accept when the server didn't report a version (best effort)
                # or when the publish is for our version or newer.
                if (
                    published_version is None
                    or expected_version is None
                    or published_version >= expected_version
                ):
                    return diagnostics
            if asyncio.get_event_loop().time() >= deadline:
                break
            await asyncio.sleep(0.05)

        # Push never arrived — try pull-diagnostics as a last resort.
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
            {"textDocument": {"uri": self._path_to_uri(file_path)}},
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
                "textDocument": {"uri": self._path_to_uri(file_path)},
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

        # Some servers support prepareRename
        try:
            prepare_request = JSONRPCMessage.create_request(
                "textDocument/prepareRename",
                {
                    "textDocument": {"uri": self._path_to_uri(file_path)},
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
                "textDocument": {"uri": self._path_to_uri(file_path)},
                "position": {"line": line, "character": character},
                "newName": new_name,
            },
            self._next_id(),
        )

        result = await self._send_request_raw(request)
        if result and isinstance(result, dict):
            workspace_edit = result
            if dry_run:
                return workspace_edit  # Return the edit without applying
            # Option (a): actually apply the WorkspaceEdit to disk. We parse
            # the LSP ``changes`` / ``documentChanges`` payload and write the
            # text edits ourselves. ``applied`` flags whether every edit
            # landed so callers never report success for an unwritten edit.
            applied = self._apply_workspace_edit(workspace_edit)
            return {**workspace_edit, "applied": applied}
        return None

    def _apply_workspace_edit(self, workspace_edit: dict) -> bool:
        """Apply an LSP ``WorkspaceEdit`` to the files on disk.

        Handles both the ``changes`` map ({uri: [TextEdit]}) and the newer
        ``documentChanges`` list of ``TextDocumentEdit`` objects. Returns True
        only if every file edit was written successfully.
        """
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
        path = self._uri_to_path(uri)
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
