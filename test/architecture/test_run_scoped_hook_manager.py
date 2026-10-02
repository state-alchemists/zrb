"""In-run hooks fire on the run's hook manager, never straight on the singleton.

A task with its own hooks (`append_hook_factory`) binds its manager for the
run. Code that imports the process-wide `hook_manager` and calls
`execute_hooks` on it skips that task's hooks, PreToolUse denials included.
Reach the manager through `get_run_hook_manager()` (agent side) or
`get_turn_hook_manager(llm_task)` (UI side); both fall back to the singleton.
"""

import ast
import pathlib

SRC = pathlib.Path(__file__).parents[2] / "src" / "zrb"

# The module that defines the singleton and the fallback accessors.
_ALLOWED = {"llm/hook/manager.py"}


def _singleton_aliases(tree: ast.Module) -> set[str]:
    return {
        alias.asname or alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module == "zrb.llm.hook.manager"
        for alias in node.names
        if alias.name == "hook_manager"
    }


def _offenders() -> list[str]:
    found: list[str] = []
    for path in sorted(SRC.rglob("*.py")):
        rel = path.relative_to(SRC).as_posix()
        if rel in _ALLOWED:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        aliases = _singleton_aliases(tree)
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Attribute)
                and node.attr == "execute_hooks"
                and isinstance(node.value, ast.Name)
                and node.value.id in aliases
            ):
                found.append(f"{rel}:{node.lineno}")
    return found


def test_no_module_fires_hooks_straight_on_the_singleton():
    assert _offenders() == []
