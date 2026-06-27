"""
LSP server configuration registry and detection helpers.

Owns the static catalogue of supported LSP servers, a user-extensible
registry (``lsp_server_configs``), and stateless helpers for detecting
which servers are installed and choosing one for a given file.
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

    def matches_file(self, file_path: str) -> bool:
        """Check if this server handles the given file."""
        ext = Path(file_path).suffix.lower()
        return ext in self.file_extensions


class LSPServerConfigRegistry:
    """User-extensible registry of LSP server configurations.

    Seeded from the built-in ``LSP_SERVER_CONFIGS`` dict at module load.
    User-registered entries (via :meth:`register`) override built-ins of
    the same name. Callers usually go through
    ``lsp_manager.register_lsp_server()`` rather than this class directly.

    A single instance is exposed at module level as
    :data:`lsp_server_configs` — import that, not the class. Construct
    a fresh instance only in tests that need full isolation.
    """

    def __init__(self) -> None:
        self._overrides: dict[str, LSPServerConfig] = {}

    def register(self, name: str, config: LSPServerConfig) -> None:
        """Register a user LSP server config, overriding any built-in of the same *name*."""
        self._overrides[name] = config

    def get(self, name: str) -> LSPServerConfig | None:
        """Get a config by name — user override wins over built-in."""
        if name in self._overrides:
            return self._overrides[name]
        return LSP_SERVER_CONFIGS.get(name)

    def all(self) -> dict[str, LSPServerConfig]:
        """All configs (merged built-in + user overrides)."""
        result = dict(LSP_SERVER_CONFIGS)
        result.update(self._overrides)
        return result

    def clear(self) -> None:
        """Drop all user-registered entries. Intended for tests."""
        self._overrides.clear()

    def detect(self) -> dict[str, str]:
        """Detect which LSP servers are available on the system.

        Returns:
            Dict mapping server name to executable path.
        """
        available = {}
        for name, config in self.all().items():
            cmd = config.command[0]
            path = shutil.which(cmd)
            if path:
                available[name] = path
        return available

    def get_for_file(
        self, file_path: str, preferred_servers: list[str] | None = None
    ) -> LSPServerConfig | None:
        """Get the LSP server config for a given file.

        Args:
            file_path: Path to the file
            preferred_servers: Optional list of preferred server names to try first

        Returns:
            LSPServerConfig if a matching server is found, None otherwise
        """
        available = self.detect()

        if preferred_servers:
            for name in preferred_servers:
                if name in available:
                    config = self.get(name)
                    if config and config.matches_file(file_path):
                        return config

        for name in available:
            config = self.get(name)
            if config and config.matches_file(file_path):
                return config

        return None

    def detect_language(self, file_path: str) -> str | None:
        """Detect programming language from file extension."""
        ext = Path(file_path).suffix.lower()
        for config in self.all().values():
            if ext in config.file_extensions:
                return config.language_ids[0]
        return None


# Pre-configured LSP servers with auto-detection
LSP_SERVER_CONFIGS: dict[str, LSPServerConfig] = {
    # Python servers
    "pyright": LSPServerConfig(
        name="pyright",
        command=["pyright-langserver", "--stdio"],
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


#: Module-level registry singleton. Import this from user code or
#: call ``lsp_manager.register_lsp_server()`` as the preferred entry point.
lsp_server_configs = LSPServerConfigRegistry()


def detect_available_lsp_servers() -> dict[str, str]:
    """Detect which LSP servers are available on the system.

    Delegates to :data:`lsp_server_configs`.

    Returns:
        Dict mapping server name to the path/command where it's found.
    """
    return lsp_server_configs.detect()


def get_lsp_config_for_file(
    file_path: str, preferred_servers: list[str] | None = None
) -> LSPServerConfig | None:
    """Get the LSP server config for a given file.

    Delegates to :data:`lsp_server_configs`.

    Args:
        file_path: Path to the file
        preferred_servers: Optional list of preferred server names to try first

    Returns:
        LSPServerConfig if a matching server is found, None otherwise
    """
    return lsp_server_configs.get_for_file(file_path, preferred_servers)


def detect_language_from_file(file_path: str) -> str | None:
    """Detect programming language from file extension.

    Delegates to :data:`lsp_server_configs`.
    """
    return lsp_server_configs.detect_language(file_path)
