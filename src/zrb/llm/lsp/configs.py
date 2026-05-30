"""
LSP server configuration registry and detection helpers.

Owns the static catalogue of supported LSP servers and the stateless
helpers for detecting which servers are installed and choosing one for
a given file.
"""

import shutil
from dataclasses import dataclass
from pathlib import Path


@dataclass
class LSPServerConfig:
    """Configuration for an LSP server."""

    name: str
    command: list[str]
    language_ids: list[str]
    file_extensions: list[str]
    initialization_options: dict | None = None
    timeout: int = 30  # seconds
    restart_interval: int | None = None  # minutes, for auto-restart

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
        path = shutil.which(cmd)
        if path:
            available[name] = path
    return available


def get_lsp_config_for_file(
    file_path: str, preferred_servers: list[str] | None = None
) -> LSPServerConfig | None:
    """Get the LSP server config for a given file.

    Args:
        file_path: Path to the file
        preferred_servers: Optional list of preferred server names to try first

    Returns:
        LSPServerConfig if a matching server is found, None otherwise
    """
    available = detect_available_lsp_servers()

    if preferred_servers:
        for name in preferred_servers:
            if name in available:
                config = LSP_SERVER_CONFIGS.get(name)
                if config and config.matches_file(file_path):
                    return config

    for name in available:
        config = LSP_SERVER_CONFIGS.get(name)
        if config and config.matches_file(file_path):
            return config

    return None


def detect_language_from_file(file_path: str) -> str | None:
    """Detect programming language from file extension."""
    ext = Path(file_path).suffix.lower()
    for config in LSP_SERVER_CONFIGS.values():
        if ext in config.file_extensions:
            return config.language_ids[0]
    return None
