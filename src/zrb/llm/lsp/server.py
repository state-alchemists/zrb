"""
LSP Server process management and communication.

Handles starting, stopping, and communicating with Language Server Protocol servers.
"""

import asyncio
import json
from pathlib import Path
from urllib.parse import unquote, urlparse

from zrb.config.config import CFG
from zrb.context.any_context import zrb_print
from zrb.llm.lsp.configs import (
    LSP_SERVER_CONFIGS,
    LSPServerConfig,
    detect_available_lsp_servers,
    detect_language_from_file,
    get_lsp_config_for_file,
)
from zrb.llm.lsp.protocol import (
    JSONRPCMessage,
    LSPProtocol,
    LSPServerError,
    LSPTimeoutError,
)

__all__ = [
    "LSP_SERVER_CONFIGS",
    "LSPServerConfig",
    "LSPServer",
    "detect_available_lsp_servers",
    "detect_language_from_file",
    "get_lsp_config_for_file",
]


class LSPServer:
    """Manages communication with an LSP server process."""

    def __init__(
        self,
        config: LSPServerConfig,
        root_path: str,
    ):
        self.config = config
        self.root_path = root_path
        self.process: asyncio.subprocess.Process | None = None
        self.reader: asyncio.StreamReader | None = None
        self.writer: asyncio.StreamWriter | None = None
        self.request_id = 0
        self.pending_requests: dict[str | int, asyncio.Future] = {}
        self.initialized = False
        self._read_task: asyncio.Task | None = None
        self._message_buffer = ""

    @property
    def is_alive(self) -> bool:
        """Check if the server process is alive."""
        return self.process is not None and self.process.returncode is None

    async def start(self) -> bool:
        """Start the LSP server process."""
        if self.is_alive:
            return True

        try:
            # Start the process
            self.process = await asyncio.create_subprocess_exec(
                *self.config.command,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.root_path,
            )

            self.reader = self.process.stdout
            self.writer = self.process.stdin

            # Start reading responses in background
            self._read_task = asyncio.create_task(self._read_loop())

            # Initialize the server
            await self._initialize()

            zrb_print(
                f"  ✓ LSP server '{self.config.name}' started for {self.root_path}",
                plain=True,
            )
            return True

        except FileNotFoundError:
            zrb_print(f"  ✗ LSP server '{self.config.name}' not found", plain=True)
            return False
        except Exception as e:
            zrb_print(
                f"  ✗ Failed to start LSP server '{self.config.name}': {e}", plain=True
            )
            return False

    async def stop(self):
        """Stop the LSP server process."""
        if self._read_task:
            self._read_task.cancel()
            try:
                await self._read_task
            except asyncio.CancelledError:
                pass

        if self.process:
            try:
                # Send shutdown request
                if self.writer:
                    shutdown_msg = JSONRPCMessage.create_request(
                        "shutdown", None, self._next_id()
                    )
                    self.writer.write(
                        JSONRPCMessage.create_content_length_header(
                            shutdown_msg
                        ).encode()
                    )
                    await self.writer.drain()

                # Send exit notification
                if self.writer:
                    exit_msg = JSONRPCMessage.create_notification("exit")
                    self.writer.write(
                        JSONRPCMessage.create_content_length_header(exit_msg).encode()
                    )
                    await self.writer.drain()
                    self.writer.close()
                    await self.writer.wait_closed()

            except Exception:
                pass

            finally:
                try:
                    self.process.terminate()
                    await asyncio.wait_for(
                        self.process.wait(),
                        timeout=CFG.LLM_SHELL_KILL_WAIT_TIMEOUT / 1000,
                    )
                except asyncio.TimeoutError:
                    self.process.kill()
                finally:
                    self.process = None
                    self.initialized = False

    async def _initialize(self) -> bool:
        """Send initialize request to the server."""
        params = JSONRPCMessage.create_request(
            "initialize",
            {
                "processId": None,
                "rootUri": self._path_to_uri(self.root_path),
                "capabilities": LSPProtocol.CAPABILITIES,
                "clientInfo": LSPProtocol.CLIENT_INFO,
            },
            self._next_id(),
        )

        result = await self._send_request_raw(params)
        if result is not None:
            # Send initialized notification
            initialized = JSONRPCMessage.create_notification("initialized")
            await self._send_notification_raw(initialized)
            self.initialized = True
            return True
        return False

    def _next_id(self) -> int:
        """Get next request ID."""
        self.request_id += 1
        return self.request_id

    def _path_to_uri(self, path: str) -> str:
        """Convert file path to URI."""
        abs_path = Path(path).absolute()
        return "file://" + str(abs_path).replace(" ", "%20")

    def _uri_to_path(self, uri: str) -> str:
        """Convert URI to file path."""
        if uri.startswith("file://"):
            return unquote(urlparse(uri).path)
        return uri

    async def _send_request_raw(self, message: str) -> dict | None:
        """Send a raw JSON-RPC request and wait for response."""
        if not self.writer:
            return None

        future = asyncio.Future()
        request_id = json.loads(message).get("id")
        self.pending_requests[request_id] = future

        try:
            self.writer.write(
                JSONRPCMessage.create_content_length_header(message).encode()
            )
            await self.writer.drain()

            result = await asyncio.wait_for(future, timeout=self.config.timeout)
            return result
        except asyncio.TimeoutError:
            self.pending_requests.pop(request_id, None)
            raise LSPTimeoutError(
                f"Request {request_id} timed out after {self.config.timeout}s"
            )
        except Exception as e:
            self.pending_requests.pop(request_id, None)
            raise e

    async def _send_notification_raw(self, message: str):
        """Send a raw JSON-RPC notification (no response expected)."""
        if not self.writer:
            return

        self.writer.write(JSONRPCMessage.create_content_length_header(message).encode())
        await self.writer.drain()

    async def _read_loop(self):
        """Background task to read responses from the server."""
        if not self.reader:
            return

        buffer = ""
        while True:
            try:
                data = await self.reader.read(4096)
                if not data:
                    break
                buffer += data.decode("utf-8")

                # Process all complete messages in buffer
                while "\r\n\r\n" in buffer:
                    header_end = buffer.index("\r\n\r\n")
                    header = buffer[:header_end]
                    body_start = header_end + 4

                    # Parse content-length from header
                    content_length = 0
                    for line in header.split("\r\n"):
                        if line.startswith("Content-Length: "):
                            content_length = int(line[16:])
                            break

                    if len(buffer) >= body_start + content_length:
                        body = buffer[body_start : body_start + content_length]
                        buffer = buffer[body_start + content_length :]
                        self._handle_message(body)
                    else:
                        break

            except asyncio.CancelledError:
                break
            except Exception as e:
                zrb_print(f"  LSP read error: {e}", plain=True)
                break

    def _handle_message(self, body: str):
        """Handle a parsed JSON-RPC message."""
        try:
            msg = json.loads(body)

            # Check if this is a response to a pending request
            if "id" in msg:
                request_id = msg["id"]
                future = self.pending_requests.pop(request_id, None)
                if future and not future.done():
                    if "error" in msg:
                        error = msg["error"]
                        future.set_exception(
                            LSPServerError(
                                error.get("code", -1),
                                error.get("message", "Unknown error"),
                                error.get("data"),
                            )
                        )
                    elif "result" in msg:
                        future.set_result(msg["result"])

            # Handle notifications (e.g., window/logMessage)
            elif "method" in msg:
                # Could log server messages here
                params = msg.get("params", {})
                if msg["method"] == "window/logMessage" and params.get("message"):
                    # Don't spam, but could log at debug level
                    pass

        except json.JSONDecodeError:
            pass
        except Exception as e:
            zrb_print(f"  LSP message handling error: {e}", plain=True)

    # --- LSP API Methods ---

    async def goto_definition(
        self, file_path: str, line: int, character: int
    ) -> list[dict] | None:
        """Go to definition for symbol at position."""
        if not self.initialized:
            return None

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

    async def get_diagnostics(self, file_path: str) -> list[dict] | None:
        """Get diagnostics for a file."""
        if not self.initialized:
            return None

        # Note: Diagnostics are typically pushed from server via notifications
        # This requests them via pull-diagnostics if supported
        request = JSONRPCMessage.create_request(
            "textDocument/diagnostic",
            {
                "textDocument": {"uri": self._path_to_uri(file_path)},
            },
            self._next_id(),
        )

        try:
            result = await self._send_request_raw(request)
            if result and "items" in result:
                return result["items"]
            return result if isinstance(result, list) else None
        except LSPServerError:
            # Some servers don't support pull diagnostics
            return None

    async def document_symbols(self, file_path: str) -> list[dict] | None:
        """Get all symbols in a document."""
        if not self.initialized:
            return None

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
            else:
                # TODO: Apply the workspace edit
                return workspace_edit
        return None
