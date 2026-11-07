"""The two layer-0 seams reach nothing in `zrb.llm` while they load.

`agent_runner.py` and `delegation_api.py` are the modules lower layers call
instead of importing the engine package and the sub-agent package. Both work
because the package registers into them while it loads, which means the
registration module is half-built at that moment: a runtime import back into it
raises `ImportError` and only in the import order that triggers it. So the rule
is not "keep the import cheap" but "have no such import at all" — every name
these modules take from `zrb.llm` sits under `if TYPE_CHECKING:`.

The check reads the syntax tree rather than importing, so it holds for a module
that cannot be imported on its own.
"""

import ast
import pathlib

import pytest

LLM = pathlib.Path(__file__).parents[2] / "src" / "zrb" / "llm"

## Path under llm/ -> the package that registers into it while loading.
SEAMS: dict[str, str] = {
    "agent_runner.py": "zrb.llm.agent",
    "delegation_api.py": "zrb.llm.subagent",
}


def _is_type_checking(test: ast.expr) -> bool:
    return isinstance(test, ast.Name) and test.id == "TYPE_CHECKING"


def _runtime_import_targets(body: list[ast.stmt]) -> list[str]:
    targets: list[str] = []
    for node in body:
        if isinstance(node, ast.If):
            if _is_type_checking(node.test):
                continue
            targets += _runtime_import_targets(node.body)
            targets += _runtime_import_targets(node.orelse)
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0 and node.module:
                targets.append(node.module)
        elif isinstance(node, ast.Import):
            targets += [alias.name for alias in node.names]
    return targets


@pytest.mark.parametrize("relative", sorted(SEAMS), ids=sorted(SEAMS))
def test_a_seam_imports_nothing_from_zrb_at_runtime(relative):
    path = LLM / relative
    assert path.is_file(), f"{relative} is gone; drop it from SEAMS or fix the path"
    loaded = [
        module
        for module in _runtime_import_targets(ast.parse(path.read_text()).body)
        if module.split(".")[0] == "zrb"
    ]
    assert not loaded, (
        f"{relative} imports {loaded} at runtime, and {SEAMS[relative]} registers "
        "into it while that package is still loading. Put the name under "
        "`if TYPE_CHECKING:` — it is an annotation, and an annotation never runs."
    )
