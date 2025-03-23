import fnmatch
import os

from zrb.util.file import read_file, write_file

_INCLUDED_PATTERNS: list[str] = [
    "*.py",  # Python
    "*.go",  # Go
    "*.rs",  # Rust
    "*.js",  # JavaScript
    "*.ts",  # TypeScript
    "*.java",  # Java
    "*.c",  # C
    "*.cpp",  # C++
    "*.cc",  # Alternative C++ extension
    "*.cxx",  # Alternative C++ extension
    "*.rb",  # Ruby
    "*.swift",  # Swift
    "*.kt",  # Kotlin
    "*.php",  # PHP
    "*.pl",  # Perl / Prolog
    "*.pm",  # Perl module
    "*.sh",  # Shell
    "*.bat",  # Batch
    "*.ps1",  # PowerShell
    "*.R",  # R (capital)
    "*.r",  # R (lowercase)
    "*.scala",  # Scala
    "*.hs",  # Haskell
    "*.cs",  # C#
    "*.fs",  # F#
    "*.ex",  # Elixir
    "*.exs",  # Elixir script
    "*.erl",  # Erlang
    "*.hrl",  # Erlang header
    "*.dart",  # Dart
    "*.m",  # Objective-C / Matlab (note: conflicts may arise)
    "*.mm",  # Objective-C++
    "*.lua",  # Lua
    "*.jl",  # Julia
    "*.groovy",  # Groovy
    "*.clj",  # Clojure
    "*.cljs",  # ClojureScript
    "*.cljc",  # Clojure common
    "*.vb",  # Visual Basic
    "*.f90",  # Fortran
    "*.f95",  # Fortran
    "*.adb",  # Ada
    "*.ads",  # Ada specification
    "*.pas",  # Pascal
    "*.pp",  # Pascal
    "*.ml",  # OCaml
    "*.mli",  # OCaml interface
    "*.nim",  # Nim
    "*.rkt",  # Racket
    "*.d",  # D
    "*.lisp",  # Common Lisp
    "*.lsp",  # Lisp variant
    "*.cl",  # Common Lisp
    "*.scm",  # Scheme
    "*.st",  # Smalltalk
    "*.vhd",  # VHDL
    "*.vhdl",  # VHDL
    "*.v",  # Verilog
    "*.asm",  # Assembly
    "*.s",  # Assembly (alternative)
    "*.sql",  # SQL (if desired)
]

# Extended list of directories and patterns to exclude.
_EXCLUDED_PATTERNS: list[str] = [
    "venv",  # Python virtual environments
    ".venv",
    "node_modules",  # Node.js dependencies
    ".git",  # Git repositories
    "__pycache__",  # Python cache directories
    "build",  # Build directories
    "dist",  # Distribution directories
    "target",  # Build output directories (Java, Rust, etc.)
    "bin",  # Binary directories
    "obj",  # Object files directories
    ".idea",  # JetBrains IDEs
    ".vscode",  # VS Code settings
    ".eggs",  # Python eggs
]


def list_files(
    directory: str = ".",
    included_patterns: list[str] = _INCLUDED_PATTERNS,
    excluded_patterns: list[str] = _EXCLUDED_PATTERNS,
) -> list[str]:
    """List all files in a directory that match any of the included glob patterns
    and do not reside in any directory matching an excluded pattern.
    Patterns are evaluated using glob-style matching.
    """
    all_files: list[str] = []
    for root, dirs, files in os.walk(directory):
        for filename in files:
            if any(fnmatch.fnmatch(filename, pat) for pat in included_patterns):
                full_path = os.path.join(root, filename)
                if _should_exclude(full_path, excluded_patterns):
                    continue
                all_files.append(full_path)
    return all_files


def _should_exclude(full_path: str, excluded_patterns: list[str]) -> bool:
    """
    Return True if the file at full_path should be excluded based on
    the list of excluded_patterns. Patterns that include a path separator
    are applied to the full normalized path; otherwise they are matched
    against each individual component of the path.
    """
    norm_path = os.path.normpath(full_path)
    path_parts = norm_path.split(os.sep)
    for pat in excluded_patterns:
        # If the pattern seems intended for full path matching (contains a separator)
        if os.sep in pat or "/" in pat:
            if fnmatch.fnmatch(norm_path, pat):
                return True
        else:
            # Otherwise check each part of the path
            if any(fnmatch.fnmatch(part, pat) for part in path_parts):
                return True
    return False


def read_text_file(file: str) -> str:
    """Read a text file and return a string containing the file content."""
    return read_file(os.path.abspath(file))


def write_text_file(file: str, content: str):
    """Write content to a text file"""
    return write_file(os.path.abspath(file), content)


def read_all_files(
    directory: str = ".",
    included_patterns: list[str] = _INCLUDED_PATTERNS,
    excluded_patterns: list[str] = _EXCLUDED_PATTERNS,
) -> list[str]:
    """Read all files in a directory that match any of the included glob patterns
    and do not match any of the excluded glob patterns.
    Patterns are evaluated using glob-style matching.
    """
    files = list_files(directory, included_patterns, excluded_patterns)
    for index, file in enumerate(files):
        content = read_text_file(file)
        files[index] = f"# {file}\n```\n{content}\n```"
    return files
