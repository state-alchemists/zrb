"""Guards against `CFG.X` being read at import time (R3, ADR-0090 Part 3).

`zrb_init.py` is the primary configuration channel, and it loads *after*
`zrb.builtin` (and everything else) has already been imported. A `CFG.X` read
that happens while a module is being imported — a module-level assignment, or
a default argument evaluated when a `def`/`lambda` executes — freezes that
value before the user's `zrb_init.py` gets a chance to change it. The fix is
always the same: wrap the read in a callable (`lambda _: CFG.X`) so it
resolves when the value is actually needed, not when the module loads.

This walks every module under `src/zrb`, and flags a `CFG.X` `Attribute` node
unless it sits inside a function/lambda **body** (deferred until called) —
a default-argument expression in `args.defaults`/`args.kw_defaults` is
evaluated at `def` time, i.e. still at import time, and is flagged too.
"""

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).parents[2]
SRC = REPO_ROOT / "src" / "zrb"

# Paths where an import-time CFG read is correct, not a bug.
EXEMPT_PREFIXES = (
    "config/",  # the config package defines CFG; its own reads are internal
    "__main__.py",  # runs after zrb_init.py has loaded, by construction
)


def _collect_violations(tree: ast.AST) -> list[tuple[int, str]]:
    violations: list[tuple[int, str]] = []

    def visit(node: ast.AST, deferred: bool) -> None:
        if (
            isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Name)
            and node.value.id == "CFG"
            and not deferred
        ):
            violations.append((node.lineno, node.attr))

        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for default in [*node.args.defaults, *node.args.kw_defaults]:
                if default is not None:
                    visit(default, deferred)
            for decorator in node.decorator_list:
                visit(decorator, deferred)
            for stmt in node.body:
                visit(stmt, True)
            return

        if isinstance(node, ast.Lambda):
            for default in [*node.args.defaults, *node.args.kw_defaults]:
                if default is not None:
                    visit(default, deferred)
            visit(node.body, True)
            return

        for child in ast.iter_child_nodes(node):
            visit(child, deferred)

    visit(tree, False)
    return violations


def _find_violations() -> list[str]:
    found: list[str] = []
    for path in SRC.rglob("*.py"):
        rel = path.relative_to(SRC).as_posix()
        if any(rel.startswith(prefix) or rel == prefix for prefix in EXEMPT_PREFIXES):
            continue
        tree = ast.parse(path.read_text(), filename=str(path))
        for lineno, attr in _collect_violations(tree):
            found.append(f"{rel}:{lineno}: CFG.{attr}")
    return found


def test_no_cfg_read_happens_at_import_time():
    violations = _find_violations()
    assert not violations, (
        "These CFG.* reads happen at import time, before zrb_init.py has "
        "loaded, so a user's CFG.X = ... assignment there is silently "
        "ignored. Wrap the read in a callable (lambda _: CFG.X) so "
        "zrb_init.py can still change it — R3, ADR-0090 Part 3:\n"
        + "\n".join(violations)
    )
