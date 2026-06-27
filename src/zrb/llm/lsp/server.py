"""
LSP Server process management and communication.

Handles starting, stopping, and communicating with Language Server Protocol servers.
"""

import asyncio
import json
from urllib.parse import unquote, urlparse

from zrb.config.config import CFG
from zrb.context.any_context import zrb_print
from zrb.llm.lsp.configs import (
    LSP_SERVER_CONFIGS,
    LSPServerConfig,
    detect_available_lsp_servers,
    detect_language_from_file,
    get_lsp_config_for_file,
    lsp_server_configs,
)
from zrb.llm.lsp.protocol import (
    JSONRPCMessage,
    LSPProtocol,
    LSPServerError,
    LSPTimeoutError,
)
from zrb.llm.lsp.server_operations import OperationsMixin

__all__ = [
    "LSP_SERVER_CONFIGS",
    "LSPServerConfig",
    "LSPServer",
    "detect_available_lsp_servers",
    "detect_language_from_file",
    "get_lsp_config_for_file",
    "lsp_server_configs",
]


class LSPServer(OperationsMixin):
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
        self._stderr_task: asyncio.Task | None = None
        self._message_buffer = ""
        # Push-diagnostics state: most servers don't implement pull-diagnostics,
        # so we receive textDocument/publishDiagnostics notifications and cache
        # them per URI. _open_files tracks which files we've sent didOpen for,
        # so subsequent edits go through didChange. Versions are incremented
        # on every didChange as required by the LSP spec.
        #
        # Cache entries are (version_or_None, diagnostics_list). The version
        # lets get_diagnostics reject late publishes from a previous didChange:
        # a server may publish for version N after we already sent didChange
        # for N+1, and we'd otherwise return stale results. Servers that don't
        # send a version (older/non-conforming) fall through as best-effort.
        self._diagnostics: dict[str, tuple[int | None, list[dict]]] = {}
        self._open_files: set[str] = set()
        self._versions: dict[str, int] = {}

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
            # Drain stderr so a server that logs verbosely (e.g. node/pyright)
            # can't fill the pipe buffer and block on its own stderr writes,
            # which would stall every request.
            self._stderr_task = asyncio.create_task(self._drain_stderr())

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
        for task in (self._read_task, self._stderr_task):
            if task:
                task.cancel()
                try:
                    await task
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
        """Convert file path to URI.

        Delegates to the canonical encoder in ``LSPProtocol`` so the URIs we
        send in didOpen/didChange match the ones used for diagnostics lookups
        and query results. A bespoke ``replace(" ", "%20")`` only handled
        spaces and left ``#``/``?``/``%``/non-ASCII characters unescaped,
        causing URI mismatches.
        """
        return LSPProtocol.create_text_document_identifier(path)["uri"]

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
        """Background task to read responses from the server.

        Works entirely in BYTES until a complete message body is sliced out,
        then decodes that body. Two correctness requirements drove this:

        * ``Content-Length`` is a **byte** count (LSP spec). Buffering a decoded
          ``str`` and slicing by that count mis-frames any message containing
          non-ASCII (e.g. an em-dash in a diagnostic) because byte length ≠
          character length.
        * Decoding each raw ``read()`` chunk individually raises
          ``UnicodeDecodeError`` whenever a multi-byte sequence straddles a read
          boundary — which killed the whole read loop, hanging every pending
          request until timeout (the pyright symptom).
        """
        if not self.reader:
            return

        buffer = b""
        while True:
            try:
                data = await self.reader.read(4096)
                if not data:
                    break
                buffer += data

                # Process all complete messages in buffer
                while b"\r\n\r\n" in buffer:
                    header_end = buffer.index(b"\r\n\r\n")
                    header = buffer[:header_end]
                    body_start = header_end + 4

                    # Parse content-length (bytes) from header
                    content_length = 0
                    for line in header.split(b"\r\n"):
                        if line.lower().startswith(b"content-length:"):
                            content_length = int(line.split(b":", 1)[1].strip())
                            break

                    if len(buffer) >= body_start + content_length:
                        body = buffer[body_start : body_start + content_length]
                        buffer = buffer[body_start + content_length :]
                        self._handle_message(body.decode("utf-8"))
                    else:
                        break

            except asyncio.CancelledError:
                break
            except Exception as e:
                zrb_print(f"  LSP read error: {e}", plain=True)
                break

    async def _drain_stderr(self):
        """Continuously discard the server's stderr so its pipe never fills."""
        stderr = self.process.stderr if self.process else None
        if stderr is None:
            return
        while True:
            try:
                data = await stderr.read(4096)
                if not data:
                    break
            except asyncio.CancelledError:
                break
            except Exception:
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

            # Handle server-originated notifications.
            elif "method" in msg:
                method = msg["method"]
                params = msg.get("params", {})
                if method == "textDocument/publishDiagnostics":
                    uri = params.get("uri")
                    if uri:
                        # Overwrite with the latest set — pylsp/pyright/etc.
                        # always publish the complete set per analysis pass.
                        # Capture the document version (optional per spec) so
                        # get_diagnostics can reject stale publishes.
                        version = params.get("version")
                        self._diagnostics[uri] = (
                            version,
                            params.get("diagnostics") or [],
                        )
                elif method == "window/logMessage" and params.get("message"):
                    # Don't spam, but could log at debug level
                    pass

        except json.JSONDecodeError:
            pass
        except Exception as e:
            zrb_print(f"  LSP message handling error: {e}", plain=True)
