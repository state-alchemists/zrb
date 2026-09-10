"""Every name an example imports from zrb must exist.

`examples/` is excluded from pytest (`norecursedirs`) and from the pyright
run (`pyright src/zrb`), so a rename in a public module leaves the examples
broken with nothing to say so — and they are the first code a new user runs.

Imports are resolved without executing the examples: a `zrb_init.py`
registers tasks on the global `cli` and some open sockets or read a camera.
"""

import ast
import importlib
from pathlib import Path

import pytest

EXAMPLES = Path(__file__).parents[2] / "examples"


def _zrb_imports(tree: ast.Module):
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            if node.module == "zrb" or node.module.startswith("zrb."):
                yield node.module, [a.name for a in node.names]
        elif isinstance(node, ast.Import):
            for a in node.names:
                if a.name == "zrb" or a.name.startswith("zrb."):
                    yield a.name, []


@pytest.mark.parametrize(
    "path", sorted(EXAMPLES.rglob("*.py")), ids=lambda p: str(p.relative_to(EXAMPLES))
)
def test_example_imports_resolve(path: Path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for module_name, names in _zrb_imports(tree):
        module = importlib.import_module(module_name)
        missing = [n for n in names if n != "*" and not hasattr(module, n)]
        assert not missing, (
            f"{path.relative_to(EXAMPLES)} imports {missing} from "
            f"{module_name}, which no longer exports them. Update the example "
            "in the same change that renamed them."
        )
