"""
LSP JSON-RPC Protocol implementation.

Handles communication with Language Server Protocol servers using JSON-RPC 2.0.
"""

import json
import uuid
from enum import Enum
from pathlib import Path
from typing import Any
from urllib.parse import quote


class LSPError(Exception):
    """Base exception for LSP operations."""

    pass


class LSPTimeoutError(LSPError):
    """Error when LSP request times out."""

    pass


class LSPServerError(LSPError):
    """Error from LSP server response."""

    def __init__(self, code: int, message: str, data: Any = None):
        self.code = code
        self.message = message
        self.data = data
        super().__init__(f"LSP Error {code}: {message}")


class SymbolKind(Enum):
    """Symbol kinds from LSP."""

    FILE = 1
    MODULE = 2
    NAMESPACE = 3
    PACKAGE = 4
    CLASS = 5
    METHOD = 6
    PROPERTY = 7
    FIELD = 8
    CONSTRUCTOR = 9
    ENUM = 10
    INTERFACE = 11
    FUNCTION = 12
    VARIABLE = 13
    CONSTANT = 14
    STRING = 15
    NUMBER = 16
    BOOLEAN = 17
    ARRAY = 18
    OBJECT = 19
    KEY = 20
    NULL = 21
    ENUM_MEMBER = 22
    STRUCT = 23
    EVENT = 24
    OPERATOR = 25
    TYPE_PARAMETER = 26

    @classmethod
    def name_for_kind(cls, kind: int) -> str:
        """Get human-readable name for symbol kind."""
        for member in cls:
            if member.value == kind:
                return member.name.lower().replace("_", " ")
        return "unknown"


class JSONRPCMessage:
    """JSON-RPC 2.0 message handling."""

    @staticmethod
    def create_request(
        method: str,
        params: dict | None = None,
        request_id: str | int | None = None,
    ) -> str:
        """Create a JSON-RPC request message."""
        if request_id is None:
            request_id = str(uuid.uuid4())
        message: dict[str, Any] = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
        }
        if params is not None:
            message["params"] = params
        return json.dumps(message)

    @staticmethod
    def create_notification(method: str, params: dict | None = None) -> str:
        """Create a JSON-RPC notification message (no response expected)."""
        message: dict[str, Any] = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            message["params"] = params
        return json.dumps(message)

    @staticmethod
    def create_content_length_header(content: str) -> str:
        """Create the content-length header for LSP communication.

        LSP uses a simple protocol:
        Content-Length: <length>\r\n
        \r\n
        <content>
        """
        return f"Content-Length: {len(content)}\r\n\r\n{content}"


class LSPProtocol:
    """Handles LSP protocol-level communication."""

    # LSP Initialize parameters
    CLIENT_INFO = {"name": "zrb-lsp-client", "version": "1.0.0"}

    CAPABILITIES = {
        "textDocument": {
            "definition": {"linkSupport": True},
            "references": {"linkSupport": True},
            "rename": {"prepareSupport": True},
            "hover": {"contentFormat": ["markdown", "plaintext"]},
            "documentSymbol": {
                "symbolKind": {"valueSet": list(range(1, 27))},
                "hierarchicalDocumentSymbolSupport": True,
            },
            "publishDiagnostics": {"relatedInformation": True},
        },
        "workspace": {
            "symbol": {"symbolKind": {"valueSet": list(range(1, 27))}},
            "didChangeConfiguration": {"dynamicRegistration": False},
        },
    }

    @classmethod
    def create_text_document_identifier(cls, file_path: str) -> dict:
        """Create TextDocumentIdentifier for a file."""

        abs_path = Path(file_path).absolute()
        return {"uri": "file://" + quote(str(abs_path), safe="/")}
