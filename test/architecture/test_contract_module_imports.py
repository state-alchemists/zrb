"""A contract module reaches nothing but the standard library and its siblings.

Every `any_*.py` exists to be depended on, so its own imports must be inert. A
runtime import of anything else makes `import zrb.llm.any_x` load machinery the
importer never asked for — and when that machinery names the contract back, it
closes a cycle that appears only once the contract is nested inside the package
it describes. Annotations are unevaluated strings under
`from __future__ import annotations`, so a name that is only ever a type can sit
under `if TYPE_CHECKING:` at no cost to the type checker.

A contract may still import a sibling contract: `AnyUI` builds its class
hierarchy from the five role ABCs, which is a runtime need, not a type one.
"""

import ast
import pathlib
import sys

import pytest

LLM = pathlib.Path(__file__).parents[2] / "src" / "zrb" / "llm"
CONTRACTS = sorted(LLM.rglob("any_*.py"))


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


def _is_sibling_contract(module: str) -> bool:
    return module.rsplit(".", 1)[-1].startswith("any_")


@pytest.mark.parametrize("path", CONTRACTS, ids=lambda path: path.name)
def test_a_contract_imports_only_the_standard_library_and_its_siblings(path):
    for module in _runtime_import_targets(ast.parse(path.read_text()).body):
        in_stdlib = module.split(".")[0] in sys.stdlib_module_names
        assert in_stdlib or _is_sibling_contract(module), (
            f"{path.name} imports {module!r} at runtime. If the name is only a "
            "type, put the import under `if TYPE_CHECKING:` — a contract that "
            "executes an import drags its target into every module that names "
            "the contract."
        )


def test_the_contract_set_is_not_empty():
    """A moved directory must fail loudly instead of passing over no files."""
    assert CONTRACTS, f"no any_*.py found under {LLM}"
