"""Every import inside `src/zrb` names its module from the root.

A relative import (`from .manager import X`) says where a name is *without*
saying which package it is in: a reader landing on the file has to count the
dots, and a tool that reasons about the import graph has to reconstruct the
package from the path. Both are avoidable, and the tree already asks a lot of a
reader — the layering ratchet has to resolve every relative import back to an
absolute one (`_imported_modules`) before it can score it, which is the same
reconstruction done a second time in a test.

One rule, one owner: the package `__init__` re-exports, and every import says
`zrb.…` in full.
"""

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).parents[2]
SRC = REPO_ROOT / "src" / "zrb"


def _label(path: Path) -> str:
    """*path* relative to the repository when it is inside it, else as given."""
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def _relative_imports(path: Path) -> list[str]:
    """`file:line: statement` for each relative import in *path*.

    Read through `ast`, so a docstring or a comment that spells `from .x import y`
    is prose, not an import — a text search would report it.
    """
    found: list[str] = []
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if not isinstance(node, ast.ImportFrom) or not node.level:
            continue
        statement = f"from {'.' * node.level}{node.module or ''} import ..."
        found.append(f"{_label(path)}:{node.lineno}: {statement}")
    return found


def test_no_module_in_src_imports_relative_to_itself():
    offenders = [hit for path in SRC.rglob("*.py") for hit in _relative_imports(path)]
    assert not offenders, (
        "src/zrb has a relative import; name the module from the root instead: "
        + "; ".join(offenders)
    )


def test_the_guard_reads_imports_not_prose(tmp_path):
    """A docstring that mentions a relative import is documentation, not code."""
    sample = tmp_path / "sample.py"
    sample.write_text(
        '"""Written as `from .manager import X` before this rule."""\n'
        "from zrb.llm.ui.any_ui import AnyUI\n",
        encoding="utf-8",
    )
    assert _relative_imports(sample) == []

    offending = tmp_path / "offending.py"
    offending.write_text("from .manager import X\n", encoding="utf-8")
    assert len(_relative_imports(offending)) == 1
