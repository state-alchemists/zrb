"""Ratchet the import direction inside ``zrb.llm`` downward.

Every ``llm/`` unit (a subpackage, or a loose top-level module) sits in one
layer, and a layer imports only from itself and the layers below:

    L0 contracts      protocols, shared types, ambient state, leaf helpers
    L1 capabilities   tools, hooks, permissions, prompt, skills, LSP, snapshots
    L2 engine         the agent run loop, summarizer
    L3 orchestration  tasks, sub-agents, custom commands
    L4 presentation   UIs and the optional voice/camera/screenshot features

A module whose job is to be depended on counts as L0 wherever it lives: the
``any_*.py`` protocols and ``agent/types.py`` (the pydantic-ai type facade).
A package may also hold a floor beneath its own layer — see
``_FLOOR_PREFIXES``.

The two allowlists below are today's debt. They may only shrink: remove a
line when you fix it, and never add one to admit new code. To fix an upward
edge, move the shared piece down to L0, or put a Protocol in L0 and let the
upper layer register the implementation (``agent_state.get_current_ui`` is the
pattern). Only runtime imports count; ``if TYPE_CHECKING`` blocks do not.
"""

import ast
import fnmatch
import pathlib

REPO_ROOT = pathlib.Path(__file__).parents[2]
SRC = REPO_ROOT / "src"
LLM = SRC / "zrb" / "llm"

_UNITS_BY_LAYER = {
    0: "config memory shared util",
    1: (
        "approval history_manager hook lsp permission prompt sandbox skill "
        "snapshot tool tool_call"
    ),
    2: "agent summarizer",
    3: "common_tools custom_command subagent task",
    4: "camera dictation emotion screenshot speech ui voice",
}
LAYER_OF_UNIT = {
    unit: layer for layer, units in _UNITS_BY_LAYER.items() for unit in units.split()
}

# Files that exist to be depended on, wherever they live.
_CONTRACT_NAME = "any_*.py"
_CONTRACT_PATHS = {"agent/types.py"}

# Path prefixes that sit below the layer of the package holding them. A floor is
# a part of a package that the layers beneath it must be able to build with:
# `ui/fallback/` is the plain terminal UI that a headless run needs, and it
# cannot drag `ui/` with it, so it scores L0 while its neighbours score L4. The
# unit still ends up in the allowlists above if it reaches back up.
_FLOOR_PREFIXES = {"ui/fallback/": 0}

# Upward runtime imports that exist today, as "importer -> imported" paths
# under src/zrb/llm. Fix one, delete its line.
KNOWN_UPWARD_EDGES: set[str] = {
    "agent/hook_agent.py -> subagent/manager/manager.py",
    "agent/hook_agent.py -> subagent/tool_resolver.py",
    "subagent/live_session.py -> ui/base/message_queue.py",
    "subagent/parent_message.py -> ui/buffered/ui.py",
    "task/chat/running.py -> ui/default/app/lexer.py",
    "task/chat/running.py -> ui/default/ui.py",
    "task/chat/running.py -> ui/multi/__init__.py",
    "task/chat/task.py -> ui/ui_config.py",
    "tool/delegate/runner.py -> ui/buffered/ui.py",
}

# Mutual dependencies between two units of the same layer, as "a <-> b".
KNOWN_SAME_LAYER_CYCLES: set[str] = {
    "prompt <-> tool",
    "subagent <-> task",
}


def _is_contract(path: str) -> bool:
    return path in _CONTRACT_PATHS or fnmatch.fnmatch(
        path.rsplit("/", 1)[-1], _CONTRACT_NAME
    )


def _unit(path: str) -> str:
    return path.split("/")[0].removesuffix(".py")


def _layer(path: str) -> int | None:
    for prefix, layer in _FLOOR_PREFIXES.items():
        if path.startswith(prefix):
            return layer
    return 0 if _is_contract(path) else LAYER_OF_UNIT.get(_unit(path))


def _resolve(module: str) -> str | None:
    """Map a ``zrb.llm...`` module name to its file path under ``llm/``."""
    parts = module.split(".")[2:]
    for size in range(len(parts), 0, -1):
        base = LLM.joinpath(*parts[:size])
        if base.with_suffix(".py").is_file():
            return base.with_suffix(".py").relative_to(LLM).as_posix()
        if base.is_dir():
            return (base / "__init__.py").relative_to(LLM).as_posix()
    return None


def _is_type_checking(test: ast.expr) -> bool:
    return (isinstance(test, ast.Name) and test.id == "TYPE_CHECKING") or (
        isinstance(test, ast.Attribute) and test.attr == "TYPE_CHECKING"
    )


def _imported_modules(node: ast.AST, package: list[str]) -> list[str]:
    if isinstance(node, ast.Import):
        return [alias.name for alias in node.names]
    if not isinstance(node, ast.ImportFrom):
        return []
    if node.level:
        keep = len(package) - (node.level - 1)
        base = ".".join(package[:keep] + ([node.module] if node.module else []))
    else:
        base = node.module or ""
    if not base.startswith("zrb.llm"):
        return []
    # `from pkg import name` may name a submodule rather than a symbol.
    return [base] + [f"{base}.{alias.name}" for alias in node.names]


def _runtime_imports(tree: ast.AST, package: list[str]) -> list[str]:
    found: list[str] = []

    def visit(node: ast.AST) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.If) and _is_type_checking(child.test):
                for other in child.orelse:
                    visit_one(other)
                continue
            visit_one(child)

    def visit_one(child: ast.AST) -> None:
        found.extend(_imported_modules(child, package))
        visit(child)

    visit(tree)
    return found


def _file_edges() -> set[tuple[str, str]]:
    edges: set[tuple[str, str]] = set()
    for path in sorted(LLM.rglob("*.py")):
        rel = path.relative_to(LLM).as_posix()
        package = ["zrb", "llm"] + rel.removesuffix(".py").split("/")[:-1]
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for module in _runtime_imports(tree, package):
            target = _resolve(module)
            if target and _unit(target) != _unit(rel):
                edges.add((rel, target))
    return edges


def _upward_edges() -> set[str]:
    found = set()
    for source, target in _file_edges():
        source_layer, target_layer = _layer(source), _layer(target)
        if source_layer is not None and target_layer is not None:
            if source_layer < target_layer:
                found.add(f"{source} -> {target}")
    return found


def _same_layer_cycles() -> set[str]:
    unit_edges = {(_unit(s), _unit(t)) for s, t in _file_edges()}
    found = set()
    for a, b in unit_edges:
        same = LAYER_OF_UNIT.get(a) is not None and LAYER_OF_UNIT.get(
            a
        ) == LAYER_OF_UNIT.get(b)
        if same and a < b and (b, a) in unit_edges:
            found.add(f"{a} <-> {b}")
    return found


def _present_units() -> set[str]:
    """The units `_UNITS_BY_LAYER` must describe: real modules, not artefacts.

    A directory counts only when it holds at least one `.py` file. Without that
    test, a `__pycache__` left behind by a moved module reads as a unit that
    exists but has no layer, and sends the reader hunting for code already
    gone.
    """
    units: set[str] = set()
    for path in LLM.iterdir():
        name = path.name
        if name.startswith("_") or name == "__pycache__":
            continue
        if path.is_dir():
            if any(path.rglob("*.py")):
                units.add(name)
        elif path.suffix == ".py":
            units.add(name.removesuffix(".py"))
    return units


def test_every_llm_unit_has_a_layer():
    missing = sorted(_present_units() - set(LAYER_OF_UNIT))
    assert not missing, (
        f"{missing} have no layer. Add each to _UNITS_BY_LAYER in this file; "
        "a unit you cannot place is usually two units."
    )


def test_no_layer_names_a_unit_that_moved_away():
    stale = sorted(set(LAYER_OF_UNIT) - _present_units())
    assert not stale, (
        f"{stale} are scored but no longer exist under llm/. A name left behind "
        "by a move scores nothing and hides the unit that replaced it — delete "
        "the line, and give the package it moved into a layer if it has none."
    )


def test_no_new_upward_import():
    new = sorted(_upward_edges() - KNOWN_UPWARD_EDGES)
    assert not new, (
        "A lower layer imports a higher one:\n  "
        + "\n  ".join(new)
        + "\nMove the shared piece down to L0, or depend on a Protocol "
        "defined in L0. See this file's docstring."
    )


def test_no_new_same_layer_cycle():
    new = sorted(_same_layer_cycles() - KNOWN_SAME_LAYER_CYCLES)
    assert not new, (
        "Two units of one layer import each other:\n  "
        + "\n  ".join(new)
        + "\nMove what they share into a third unit, or a lower layer."
    )


def test_the_upward_ratchet_is_tight():
    fixed = sorted(KNOWN_UPWARD_EDGES - _upward_edges())
    assert not fixed, (
        "These upward imports are gone; delete them from KNOWN_UPWARD_EDGES:\n  "
        + "\n  ".join(fixed)
    )


def test_the_cycle_ratchet_is_tight():
    fixed = sorted(KNOWN_SAME_LAYER_CYCLES - _same_layer_cycles())
    assert not fixed, (
        "These cycles are gone; delete them from KNOWN_SAME_LAYER_CYCLES:\n  "
        + "\n  ".join(fixed)
    )
