"""
LSP JSON-RPC Protocol implementation.

Handles communication with Language Server Protocol servers using JSON-RPC 2.0.
"""

import asyncio
import json
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional, Union


class LSPError(Exception):
    """Base exception for LSP operations."""

    pass


class LSPConnectionError(LSPError):
    """Error when connecting to LSP server."""

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


@dataclass
class Position:
    """Position in a text document (0-based)."""

    line: int
    character: int

    def to_dict(self) -> dict:
        return {"line": self.line, "character": self.character}


@dataclass
class Range:
    """A range in a text document."""

    start: Position
    end: Position

    def to_dict(self) -> dict:
        return {"start": self.start.to_dict(), "end": self.end.to_dict()}


@dataclass
class Location:
    """Location in a text document."""

    uri: str
    range: Range

    @classmethod
    def from_dict(cls, data: dict) -> "Location":
        return cls(
            uri=data["uri"],
            range=Range(
                start=Position(**data["range"]["start"]),
                end=Position(**data["range"]["end"]),
            ),
        )


@dataclass
class DiagnosticSeverity(Enum):
    """Diagnostic severity levels."""

    ERROR = 1
    WARNING = 2
    INFORMATION = 3
    HINT = 4


@dataclass
class Diagnostic:
    """A diagnostic message from LSP."""

    range: Range
    message: str
    severity: int = 1  # DiagnosticSeverity.ERROR
    source: Optional[str] = None
    code: Optional[Union[str, int]] = None

    @classmethod
    def from_dict(cls, data: dict) -> "Diagnostic":
        return cls(
            range=Range(
                start=Position(**data["range"]["start"]),
                end=Position(**data["range"]["end"]),
            ),
            message=data["message"],
            severity=data.get("severity", 1),
            source=data.get("source"),
            code=data.get("code"),
        )


@dataclass
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


@dataclass
class DocumentSymbol:
    """A symbol in a document."""

    name: str
    kind: int
    range: Range
    selection_range: Range
    detail: Optional[str] = None
    children: list["DocumentSymbol"] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> "DocumentSymbol":
        children = []
        for child in data.get("children", []):
            children.append(cls.from_dict(child))
        return cls(
            name=data["name"],
            kind=data["kind"],
            range=Range(
                start=Position(**data["range"]["start"]),
                end=Position(**data["range"]["end"]),
            ),
            selection_range=Range(
                start=Position(**data["selectionRange"]["start"]),
                end=Position(**data["selectionRange"]["end"]),
            ),
            detail=data.get("detail"),
            children=children,
        )


@dataclass
class SymbolInformation:
    """Workspace symbol information."""

    name: str
    kind: int
    location: Location
    container_name: Optional[str] = None

    @classmethod
    def from_dict(cls, data: dict) -> "SymbolInformation":
        return cls(
            name=data["name"],
            kind=data["kind"],
            location=Location.from_dict(data["location"]),
            container_name=data.get("containerName"),
        )


@dataclass
class Hover:
    """Hover information from LSP."""

    contents: Any  # Can be string, MarkedString, or MarkupContent
    range: Optional[Range] = None

    @classmethod
    def from_dict(cls, data: dict) -> "Hover":
        return cls(
            contents=data["contents"],
            range=(
                Range(
                    start=Position(**data["range"]["start"]),
                    end=Position(**data["range"]["end"]),
                )
                if data.get("range")
                else None
            ),
        )


class JSONRPCMessage:
    """JSON-RPC 2.0 message handling."""

    @staticmethod
    def create_request(
        method: str,
        params: Optional[dict] = None,
        request_id: Optional[Union[str, int]] = None,
    ) -> str:
        """Create a JSON-RPC request message."""
        if request_id is None:
            request_id = str(uuid.uuid4())
        message = {"jsonrpc": "2.0", "id": request_id, "method": method}
        if params is not None:
            message["params"] = params
        return json.dumps(message)

    @staticmethod
    def create_notification(method: str, params: Optional[dict] = None) -> str:
        """Create a JSON-RPC notification message (no response expected)."""
        message = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            message["params"] = params
        return json.dumps(message)

    @staticmethod
    def parse_response(
        data: str,
    ) -> tuple[Optional[Union[str, int]], Any, Optional[dict]]:
        """Parse a JSON-RPC response.

        Returns:
            Tuple of (request_id, result, error)
        """
        obj = json.loads(data)
        request_id = obj.get("id")
        result = obj.get("result")
        error = obj.get("error")
        return request_id, result, error

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
    def create_initialize_params(
        cls,
        root_path: str,
        initialization_options: Optional[dict] = None,
    ) -> dict:
        """Create parameters for initialize request."""
        from pathlib import Path
        from urllib.parse import quote

        # Convert to file URI

        def path_to_uri(p: str) -> str:
            abs_path = Path(p).absolute()
            # Properly encode the path as a file URI
            return "file://" + quote(str(abs_path), safe="/")

        return {
            "processId": None,
            "rootUri": path_to_uri(root_path),
            "capabilities": cls.CAPABILITIES,
            "clientInfo": cls.CLIENT_INFO,
            "initializationOptions": initialization_options,
        }

    @classmethod
    def create_text_document_identifier(cls, file_path: str) -> dict:
        """Create TextDocumentIdentifier for a file."""
        from pathlib import Path
        from urllib.parse import quote

        abs_path = Path(file_path).absolute()
        return {"uri": "file://" + quote(str(abs_path), safe="/")}

    @classmethod
    def create_position(cls, line: int, character: int) -> dict:
        """Create Position object."""
        return {"line": line, "character": character}
