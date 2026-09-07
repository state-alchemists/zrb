"""Static constants for `analyze_code`."""

DEFAULT_EXTENSIONS = [
    "py",
    "go",
    "java",
    "ts",
    "js",
    "rs",
    "rb",
    "php",
    "sh",
    "bash",
    "c",
    "cpp",
    "h",
    "hpp",
    "cs",
    "swift",
    "kt",
    "scala",
    "m",
    "pl",
    "lua",
    "sql",
    "html",
    "css",
    "scss",
    "less",
    "json",
    "yaml",
    "yml",
    "toml",
    "ini",
    "xml",
    "md",
    "rst",
    "txt",
]

# File extensions that LSP can analyze semantically
LSP_SUPPORTED_EXTENSIONS = {
    ".py",
    ".pyi",
    ".pyw",  # Python
    ".go",  # Go
    ".ts",
    ".tsx",
    ".js",
    ".jsx",  # TypeScript/JavaScript
    ".rs",  # Rust
    ".c",
    ".cpp",
    ".cc",
    ".cxx",
    ".h",
    ".hpp",
    ".hxx",  # C/C++
    ".rb",
    ".rake",
    ".gemspec",  # Ruby
    ".java",  # Java
    ".php",  # PHP
    ".cs",  # C#
    ".swift",  # Swift
    ".kt",
    ".kts",  # Kotlin
    ".scala",
    ".sc",  # Scala
    ".lua",  # Lua
}
