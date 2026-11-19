"""Ratchet the import direction inside ``zrb.llm`` downward.

Every ``llm/`` unit (a subpackage, or a loose top-level module) sits in one
layer, and a layer imports only from itself and the layers below:

    L0 contracts      protocols, shared types, ambient state, leaf helpers
    L1 capabilities   tools, hooks, permissions, prompt, skills, LSP, snapshots
    L2 engine         the agent run loop, summarizer
    L3 orchestration  tasks, sub-agents, custom commands
    L4 presentation   UIs and the optional voice/camera/screenshot features

A module's layer comes from where it sits. `agent/types.py` is the one
exemption: it re-exports the pydantic-ai types the run loop hands around by the
names the framework gave them. A contract a lower layer must name is *placed*
where that layer can reach it — under `contracts/` — rather than scored L0 by
its filename, because a rank granted by a name is invisible in the path. A
package may also hold a floor beneath its own layer — see `_FLOOR_PREFIXES`.

A unit's layer comes from one of two places while the tree is being sorted into
five directories: the directory it sits in (``_LAYERS``), or the table below for
a unit that has not moved yet. Both are legal at once, so a half-moved tree
still gets judged — and the directory wins where the two disagree.

The two allowlists below are today's debt. They may only shrink: remove a
line when you fix it, and never add one to admit new code. To fix an upward
edge, move the shared piece down to L0, or put a Protocol in L0 and let the
upper layer register the implementation (``agent_state.get_current_ui`` is the
pattern). Only runtime imports count; ``if TYPE_CHECKING`` blocks do not.
"""

import ast
import importlib.util

from llm_layers import LLM, _is_upward, _layer, _unit

# Upward runtime imports that exist today, as "importer -> imported" paths
# under src/zrb/llm. Fix one, delete its line. Empty is where this ends: a new
# upward import fails the ratchet instead of joining a list.
KNOWN_UPWARD_EDGES: set[str] = set()

# Mutual dependencies between two units of the same layer, as "a <-> b". The
# same rule as above: empty is where this ends, and the two lists are now empty.
# `subagent <-> task` was the last one — the sub-agent manager builds the chat
# task a resumed session runs as, and the chat task reaches the manager for its
# roster, so each asked the other to build what it needed.
KNOWN_SAME_LAYER_CYCLES: set[str] = set()


def _resolve(module: str) -> str | None:
    """Map a ``zrb.llm...`` module name to its file path under ``llm/``."""
    if not module.startswith("zrb.llm"):
        return None
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


_IMPORT_CALLS = {"import_module", "__import__"}


def _absolute_name(name: str, package: list[str] | None) -> str | None:
    """Resolve a dotted name that may start with dots against *package*.

    `from ..shared import x` in `zrb/llm/task/chat/` is `zrb.llm.task.shared`,
    and so is `import_module("..shared", package="zrb.llm.task.chat")`: the two
    spellings follow the same level rule. Without a package an absolute name
    still reads; a relative one cannot.
    """
    level = len(name) - len(name.lstrip("."))
    if not level:
        return name
    if package is None:
        return None
    keep = len(package) - (level - 1)
    if keep < 1:
        return None
    remainder = name[level:]
    return ".".join(package[:keep] + ([remainder] if remainder else []))


def _imported_modules(node: ast.AST, package: list[str] | None) -> list[str]:
    if isinstance(node, ast.Import):
        return [alias.name for alias in node.names]
    if not isinstance(node, ast.ImportFrom):
        return []
    base = _absolute_name("." * node.level + (node.module or ""), package)
    if not base:
        return []
    # `from pkg import name` may name a submodule rather than a symbol.
    return [base] + [f"{base}.{alias.name}" for alias in node.names]


def _import_call_name(func: ast.AST) -> str:
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return ""


def _runtime_imports(tree: ast.AST, package: list[str] | None = None) -> list[str]:
    """Every module name a runtime import in *tree* can reach.

    Covers the three spellings: `import a.b`, `from a.b import name` (which may
    name a submodule), and `import_module("a.b")` — each in its absolute and its
    dotted-relative form. A `TYPE_CHECKING` block is skipped: the ratchet's own
    rule is about the import a run pays for. `package` is the importing file's
    own package, which is what a relative name resolves against; without it
    such a name is dropped.
    """
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
        if (
            isinstance(child, ast.Call)
            and _import_call_name(child.func) in _IMPORT_CALLS
        ):
            found.extend(_import_call_targets(child, package))
        visit(child)

    visit(tree)
    return found


def _import_call_targets(call: ast.Call, package: list[str] | None) -> list[str]:
    """The module an `import_module("a.b")` call names, if it names one."""
    argument = call.args[0] if call.args else None
    if not (isinstance(argument, ast.Constant) and isinstance(argument.value, str)):
        return []
    target = _absolute_name(argument.value, _call_package(call, package))
    return [target] if target else []


def _call_package(call: ast.Call, package: list[str] | None) -> list[str] | None:
    """The package an `import_module` call resolves a relative name against.

    Python takes the anchor from the `package=` keyword and nowhere else: a
    literal string names it, `__package__` means the importing file's own
    package, and a name the ratchet cannot follow falls back to that same
    package — the anchor every caller in this tree passes.
    """
    keyword = next((word for word in call.keywords if word.arg == "package"), None)
    value = keyword.value if keyword else None
    if isinstance(value, ast.Constant) and isinstance(value.value, str):
        return value.value.split(".") if value.value else None
    return package


def _runtime_import_names(source: str, package: list[str] | None = None) -> set[str]:
    """The module names *source* reaches at runtime, in every spelling."""
    return set(_runtime_imports(ast.parse(source), package))


def _package_of(rel: str) -> list[str]:
    """The package a file under `llm/` is imported as, read from its path.

    The file's own name is dropped: a module's package is the directory it sits
    in, and an `__init__.py` *is* that directory — `llm/capabilities/tool/__init__.py`
    anchors a relative name at `zrb.llm.capabilities.tool`, exactly as Python does.
    """
    return ["zrb", "llm"] + rel.removesuffix(".py").split("/")[:-1]


def test_an_import_spelled_as_a_call_is_an_edge():
    """`import_module("a.b")` reaches the module `import a.b` reaches.

    The edge set is built from this collector, so a spelling it cannot read is
    an upward import the ratchet cannot see — and a deferred import upward is
    an import upward however it is spelled.
    """
    names = _runtime_imports(ast.parse('importlib.import_module("zrb.llm.ui.session")'))
    assert "zrb.llm.ui.session" in names


def test_a_relative_import_resolves_against_the_importing_package():
    """`from ..shared import x` is an edge to `zrb.llm.task.shared`."""
    names = _runtime_imports(
        ast.parse("from ..shared import prompt_text"), ["zrb", "llm", "task", "chat"]
    )
    assert "zrb.llm.task.shared" in names


def test_a_relative_import_module_resolves_its_own_package():
    """`import_module("..ui", package=__package__)` is an edge to `zrb.llm.ui`."""
    names = _runtime_imports(
        ast.parse('importlib.import_module("..ui", package=__package__)'),
        ["zrb", "llm", "agent"],
    )
    assert "zrb.llm.ui" in names


def test_a_relative_import_module_resolves_a_literal_package():
    """`package=` anchors a relative name exactly as Python anchors it.

    Not `zrb.llm.ui`: the anchor is the dotted name given, so `..ui` from
    `zrb.llm.engine.agent.loader` is `zrb.llm.engine.agent.ui`. Asked of `importlib` itself,
    so this expectation cannot drift from the rule it describes.
    """
    source = 'importlib.import_module("..ui", package="zrb.llm.engine.agent.loader")'
    resolved = importlib.util.resolve_name("..ui", "zrb.llm.engine.agent.loader")
    assert resolved in _runtime_imports(ast.parse(source))


def test_a_package_init_file_is_its_own_package():
    """A relative name in `llm/capabilities/tool/__init__.py` anchors at `zrb.llm.capabilities.tool`."""
    assert _package_of("tool/__init__.py") == ["zrb", "llm", "tool"]
    assert _package_of("tool/delegate/runner.py") == ["zrb", "llm", "tool", "delegate"]
    assert _package_of("common_tools.py") == ["zrb", "llm"]


def test_a_type_checking_block_is_not_an_edge():
    source = (
        "from typing import TYPE_CHECKING\n"
        "if TYPE_CHECKING:\n"
        "    import zrb.llm.ui.session\n"
    )
    assert "zrb.llm.ui.session" not in _runtime_imports(ast.parse(source))


def _file_edges() -> set[tuple[str, str]]:
    edges: set[tuple[str, str]] = set()
    for path in sorted(LLM.rglob("*.py")):
        rel = path.relative_to(LLM).as_posix()
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for module in _runtime_imports(tree, _package_of(rel)):
            target = _resolve(module)
            if target and _unit(target) != _unit(rel):
                edges.add((rel, target))
    return edges


def _upward_edges() -> set[str]:
    return {
        f"{source} -> {target}"
        for source, target in _file_edges()
        if _is_upward(source, target)
    }


def _same_layer_cycles() -> set[str]:
    unit_edges = {(_unit(s), _unit(t)) for s, t in _file_edges()}
    found = set()
    for a, b in unit_edges:
        a_layer = _layer(a)
        if (
            a_layer is not None
            and a_layer == _layer(b)
            and a < b
            and (b, a) in unit_edges
        ):
            found.add(f"{a} <-> {b}")
    return found


RUNNER = "zrb.runner"
"""The CLI package the engine must never import — see `test_llm_never_imports_it`."""


def _lazy_export_targets() -> dict[str, str]:
    """The modules `zrb`'s own lazy export table hides behind a name.

    `from zrb import cli` is the same edge as `from zrb.runner.cli import cli`,
    and the string alone does not say so: `zrb/__init__.py` maps `cli` to
    `zrb.runner.cli`. Read from the package, so a re-export added there is
    covered the day it lands.
    """
    import zrb

    exports = getattr(zrb, "_LAZY_EXPORTS", {})
    return {f"zrb.{name}": module for name, module in exports.items()}


def _runner_reaches_in(source: str, package: list[str] | None = None) -> list[str]:
    """The runner modules *source* imports at runtime, however it spells them.

    `package` is the importing file's own package, so `from ...runner import cli`
    — which Python resolves to `zrb.runner` — is an edge here too, not only the
    absolute spelling and the call.
    """
    lazy = _lazy_export_targets()
    reached = {lazy.get(name, name) for name in _runtime_import_names(source, package)}
    hits = {m for m in reached if m == RUNNER or m.startswith(f"{RUNNER}.")}
    # `from zrb.runner.cli import cli` also names `zrb.runner.cli.cli`: the
    # parent is the module the import reaches, the child only its symbol.
    return sorted(m for m in hits if m.rsplit(".", 1)[0] not in hits)


def _files_reaching_the_runner() -> list[str]:
    found: list[str] = []
    for path in sorted(LLM.rglob("*.py")):
        rel = path.relative_to(LLM).as_posix()
        source = path.read_text(encoding="utf-8")
        for module in _runner_reaches_in(source, _package_of(rel)):
            found.append(f"{rel} -> {module}")
    return found


def test_the_runner_guard_sees_every_spelling():
    """A guard that only ever reports "clean" is a guard nobody has tested.

    These are the shapes an editor writes when it auto-imports, or a reviewer
    reaches for the documented re-export; each one reaches the CLI at runtime.
    """
    assert _runner_reaches_in("from zrb.runner.cli import cli") == ["zrb.runner.cli"]
    assert _runner_reaches_in("from zrb import cli") == ["zrb.runner.cli"]
    assert _runner_reaches_in("from zrb import runner") == ["zrb.runner"]
    assert _runner_reaches_in("import zrb.runner.web_app") == ["zrb.runner.web_app"]
    assert _runner_reaches_in("importlib.import_module('zrb.runner.cli')") == [
        "zrb.runner.cli"
    ]
    assert _runner_reaches_in("from zrb.llm.capabilities.tool.shell import run_shell_command") == []
    assert _runner_reaches_in("from typing import TYPE_CHECKING\n") == []
    assert (
        _runner_reaches_in("if TYPE_CHECKING:\n    from zrb.runner.cli import cli\n")
        == []
    )


def test_the_runner_guard_resolves_a_relative_import():
    """`from ...runner import cli`, in `llm/capabilities/tool/`, reaches `zrb.runner` too.

    The scan reads a file's text and its package from its path; without the
    package, this spelling resolves to nothing and the guard reports a clean
    tree it never looked at.
    """
    tool_package = _package_of("tool/some_tool.py")
    # `zrb.runner` wins over `zrb.runner.cli`: the import reaches the package,
    # and the name after `import` is a symbol it may or may not be a module.
    assert _runner_reaches_in("from ...runner import cli", tool_package) == [
        "zrb.runner"
    ]
    assert _runner_reaches_in(
        'importlib.import_module("...runner.cli", package=__package__)', tool_package
    ) == ["zrb.runner.cli"]
    # One level too shallow: `from ..runner import cli` in `llm/capabilities/tool/` is
    # `zrb.llm.runner`, which does not exist — and is not the CLI.
    assert _runner_reaches_in("from ..runner import cli", tool_package) == []


def test_llm_never_imports_the_runner():
    """The engine is what the CLI is built on, so it cannot be built with the CLI.

    ``zrb.runner`` creates the group tree, the session logger and the web
    server; ``zrb.llm`` runs agents. The one runtime edge this forbids was
    ``tool/zrb_task.py -> runner/cli.py``, to reach the root group the task tool
    walks: it made every process that builds an agent import the server stack,
    and it tied the tools to a singleton the caller could not choose. The tree is
    registered in ``zrb/group/root_group.py`` instead — the same register-and-read
    seam ``agent_state.get_current_ui`` uses.
    """
    offenders = _files_reaching_the_runner()
    assert not offenders, (
        "The engine imports the CLI:\n  "
        + "\n  ".join(offenders)
        + "\nPut what both sides need in a lower package and register it there; "
        "see zrb/group/root_group.py for the pattern."
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
