"""Every text-mode file operation in shipped code names its encoding.

Python falls back to the *locale* encoding when `encoding=` is omitted. On
Linux and macOS that is UTF-8, so the omission is invisible; on a Windows
runner it is cp1252, and the first non-ASCII byte raises UnicodeDecodeError.

That is exactly how `scripts/build_pypi_readme.py` failed the moment Windows
joined the CI matrix -- `README.md`'s first emoji, at byte 692:

    UnicodeDecodeError: 'charmap' codec can't decode byte 0x8f in position 692

The bug class is undetectable on the platforms most of this project's
development happens on, which is why it needs a static check rather than a
test that happens to touch the affected path.

Scope is `src/zrb` and `scripts`: the code that ships and the code that builds
what ships. `test/` is deliberately excluded -- it has ~400 such calls, nearly
all writing ASCII fixtures into tmp_path, where the locale default is harmless.
The Windows CI job exercises those for real; a fixture that needs an encoding
will say so by failing there.
"""

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).parents[2]
SCANNED_DIRS = ("src/zrb", "scripts")
TEXT_IO_METHODS = frozenset({"read_text", "write_text"})


def _has_encoding(call: ast.Call) -> bool:
    return any(kw.arg == "encoding" for kw in call.keywords)


def _is_binary_open(call: ast.Call) -> bool:
    """True when `open()`'s mode argument requests binary, where encoding is illegal."""
    mode = next(
        (kw.value for kw in call.keywords if kw.arg == "mode"),
        call.args[1] if len(call.args) > 1 else None,
    )
    return isinstance(mode, ast.Constant) and "b" in str(mode.value)


def _offenders_in(path: Path) -> list[str]:
    found = []
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if not isinstance(node, ast.Call) or _has_encoding(node):
            continue
        func = node.func
        # `p.read_text()` / `p.write_text(...)`
        if isinstance(func, ast.Attribute) and func.attr in TEXT_IO_METHODS:
            found.append(f"{path.relative_to(REPO_ROOT)}:{node.lineno} .{func.attr}()")
        # the builtin `open(...)`, but not `something.open(...)`
        elif isinstance(func, ast.Name) and func.id == "open":
            if not _is_binary_open(node):
                found.append(f"{path.relative_to(REPO_ROOT)}:{node.lineno} open()")
    return found


def test_shipped_code_never_relies_on_the_locale_encoding():
    offenders = [
        entry
        for directory in SCANNED_DIRS
        for source in sorted((REPO_ROOT / directory).rglob("*.py"))
        for entry in _offenders_in(source)
    ]
    assert not offenders, (
        "Text file I/O without an explicit `encoding=` reads as UTF-8 on Linux "
        "and cp1252 on Windows. Pass encoding='utf-8':\n  " + "\n  ".join(offenders)
    )
