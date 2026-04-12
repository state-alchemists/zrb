"""
LSP Server process management and communication.

Handles starting, stopping, and communicating with Language Server Protocol servers.
"""

import asyncio
import json
import os
import shutil
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional, Union
from urllib.parse import unquote, urlparse

from zrb.config.config import CFG
from zrb.context.any_context import zrb_print
from zrb.llm.lsp.protocol import (
    JSONRPCMessage,
    LSPError,
    LSPProtocol,
    LSPServerError,
    LSPTimeoutError,
)


@dataclass
class LSPServerConfig:
    """Configuration for an LSP server."""

    name: str
    command: list[str]
    language_ids: list[str]
    file_extensions: list[str]
    initialization_options: Optional[dict] = None
    timeout: int = 30  # seconds
    restart_interval: Optional[int] = None  # minutes, for auto-restart

    def matches_file(self, file_path: str) -> bool:
        """Check if this server handles the given file."""
        ext = Path(file_path).suffix.lower()
        return ext in self.file_extensions


# Pre-configured LSP servers with auto-detection
LSP_SERVER_CONFIGS: dict[str, LSPServerConfig] = {
    # Python servers
    "pyright": LSPServerConfig(
        name="pyright",
        command=["pyright", "--stdio"],
        language_ids=["python"],
        file_extensions=[".py", ".pyi", ".pyw"],
        initialization_options=None,
    ),
    "pylsp": LSPServerConfig(
        name="pylsp",
        command=["pylsp"],
        language_ids=["python"],
        file_extensions=[".py", ".pyi", ".pyw"],
        initialization_options=None,
    ),
    "jedi": LSPServerConfig(
        name="jedi-language-server",
        command=["jedi-language-server"],
        language_ids=["python"],
        file_extensions=[".py", ".pyi", ".pyw"],
    ),
    # Go
    "gopls": LSPServerConfig(
        name="gopls",
        command=["gopls", "serve"],
        language_ids=["go"],
        file_extensions=[".go"],
    ),
    # TypeScript/JavaScript
    "typescript-language-server": LSPServerConfig(
        name="typescript-language-server",
        command=["typescript-language-server", "--stdio"],
        language_ids=["typescript", "javascript", "typescriptreact", "javascriptreact"],
        file_extensions=[".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"],
    ),
    # Rust
    "rust-analyzer": LSPServerConfig(
        name="rust-analyzer",
        command=["rust-analyzer"],
        language_ids=["rust"],
        file_extensions=[".rs"],
    ),
    # C/C++
    "clangd": LSPServerConfig(
        name="clangd",
        command=["clangd"],
        language_ids=["c", "cpp"],
        file_extensions=[".c", ".cpp", ".cc", ".cxx", ".h", ".hpp", ".hxx"],
    ),
    # Ruby
    "ruby-lsp": LSPServerConfig(
        name="ruby-lsp",
        command=["ruby-lsp"],
        language_ids=["ruby"],
        file_extensions=[".rb", ".rake", ".gemspec"],
    ),
    "solargraph": LSPServerConfig(
        name="solargraph",
        command=["solargraph", "stdio"],
        language_ids=["ruby"],
        file_extensions=[".rb", ".rake", ".gemspec"],
    ),
    # Java
    "jdtls": LSPServerConfig(
        name="jdtls",
        command=["jdtls"],
        language_ids=["java"],
        file_extensions=[".java"],
    ),
    # PHP
    "intelephense": LSPServerConfig(
        name="intelephense",
        command=["intelephense", "--stdio"],
        language_ids=["php"],
        file_extensions=[".php", ".phtml", ".php3", ".php4", ".php5"],
    ),
    # C#
    "omnisharp": LSPServerConfig(
        name="omnisharp",
        command=["omnisharp", "-lsp"],
        language_ids=["csharp"],
        file_extensions=[".cs"],
    ),
    "csharp-ls": LSPServerConfig(
        name="csharp-ls",
        command=["csharp-ls", "--stdio"],
        language_ids=["csharp"],
        file_extensions=[".cs"],
    ),
    # Swift
    "sourcekit-lsp": LSPServerConfig(
        name="sourcekit-lsp",
        command=["sourcekit-lsp"],
        language_ids=["swift"],
        file_extensions=[".swift"],
    ),
    # Kotlin
    "kotlin-language-server": LSPServerConfig(
        name="kotlin-language-server",
        command=["kotlin-language-server"],
        language_ids=["kotlin"],
        file_extensions=[".kt", ".kts"],
    ),
    # Scala
    "metals": LSPServerConfig(
        name="metals",
        command=["metals"],
        language_ids=["scala"],
        file_extensions=[".scala", ".sc"],
    ),
    # Lua
    "lua-language-server": LSPServerConfig(
        name="lua-language-server",
        command=["lua-language-server"],
        language_ids=["lua"],
        file_extensions=[".lua"],
    ),
    # YAML
    "yaml-language-server": LSPServerConfig(
        name="yaml-language-server",
        command=["yaml-language-server", "--stdio"],
        language_ids=["yaml"],
        file_extensions=[".yaml", ".yml"],
    ),
    # JSON
    "json-language-server": LSPServerConfig(
        name="json-language-server",
        command=["vscode-json-languageserver", "--stdio"],
        language_ids=["json"],
        file_extensions=[".json", ".jsonc"],
    ),
    # HTML
    "html-language-server": LSPServerConfig(
        name="html-language-server",
        command=["html-languageserver", "--stdio"],
        language_ids=["html"],
        file_extensions=[".html", ".htm"],
    ),
    # CSS
    "css-language-server": LSPServerConfig(
        name="css-language-server",
        command=["css-languageserver", "--stdio"],
        language_ids=["css", "scss", "less"],
        file_extensions=[".css", ".scss", ".less"],
    ),
}


def detect_available_lsp_servers() -> dict[str, str]:
    """Detect which LSP servers are available on the system.

    Returns:
        Dict mapping server name to the path/command where it's found.
    """
    available = {}
    for name, config in LSP_SERVER_CONFIGS.items():
        cmd = config.command[0]
        # Check if command exists in PATH
        path = shutil.which(cmd)
        if path:
            available[name] = path
    return available


def get_lsp_config_for_file(
    file_path: str, preferred_servers: Optional[list[str]] = None
) -> Optional[LSPServerConfig]:
    """Get the LSP server config for a given file.

    Args:
        file_path: Path to the file
        preferred_servers: Optional list of preferred server names to try first

    Returns:
        LSPServerConfig if a matching server is found, None otherwise
    """
    available = detect_available_lsp_servers()

    # Check preferred servers first
    if preferred_servers:
        for name in preferred_servers:
            if name in available:
                config = LSP_SERVER_CONFIGS.get(name)
                if config and config.matches_file(file_path):
                    return config

    # Fall back to any available server that handles this file
    for name in available:
        config = LSP_SERVER_CONFIGS.get(name)
        if config and config.matches_file(file_path):
            return config

    return None


def detect_language_from_file(file_path: str) -> Optional[str]:
    """Detect programming language from file extension."""
    ext = Path(file_path).suffix.lower()
    for config in LSP_SERVER_CONFIGS.values():
        if ext in config.file_extensions:
            return config.language_ids[0]
    return None


class LSPServer:
    """Manages communication with an LSP server process."""

    def __init__(
        self,
        config: LSPServerConfig,
        root_path: str,
    ):
        self.config = config
        self.root_path = root_path
        self.process: Optional[asyncio.subprocess.Process] = None
        self.reader: Optional[asyncio.StreamReader] = None
        self.writer: Optional[asyncio.StreamWriter] = None
        self.request_id = 0
        self.pending_requests: dict[Union[str, int], asyncio.Future] = {}
        self.initialized = False
        self._read_task: Optional[asyncio.Task] = None
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

    async def _send_request_raw(self, message: str) -> Optional[dict]:
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
    ) -> Optional[list[dict]]:
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
    ) -> Optional[list[dict]]:
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

    async def get_diagnostics(self, file_path: str) -> Optional[list[dict]]:
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

    async def document_symbols(self, file_path: str) -> Optional[list[dict]]:
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

    async def workspace_symbols(self, query: str = "") -> Optional[list[dict]]:
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

    async def hover(self, file_path: str, line: int, character: int) -> Optional[dict]:
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
    ) -> Optional[dict]:
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
