"""Import-cycle guards: a declared allowlist, and a per-module import check.

`CIRCULAR_IMPORT_ALLOWLIST` maps a file to the number of `# lazy: circular`
workarounds it carries. It is empty: every cycle found so far was either a
mislabeled comment, or a package `__init__` re-export dragging in a sibling
nothing outside the package needed, and both are fixable at the source. A new
entry is allowed, but must land in the same diff as the cycle, with a reason
in the comment itself.

`test_every_module_imports_with_its_parents_stubbed` is the behavioural half:
the count above is blind to a cycle that carries no workaround because import
order masks it. Stubbing a module's parents strips that masking, leaving its
own import closure and nothing else.
"""

import re
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parents[2]
SRC = REPO_ROOT / "src" / "zrb"

# Path relative to src/zrb -> number of "# lazy: circular" occurrences
# expected in that file. Add an entry in the same diff that introduces a
# genuine circular-import workaround, with a reason in the comment itself.
CIRCULAR_IMPORT_ALLOWLIST: dict[str, int] = {}


def _circular_import_counts() -> dict[str, int]:
    counts: dict[str, int] = {}
    for path in SRC.rglob("*.py"):
        n = len(re.findall(r"# lazy: circular", path.read_text(encoding="utf-8")))
        if n:
            counts[path.relative_to(SRC).as_posix()] = n
    return counts


def test_circular_import_workarounds_match_the_allowlist():
    actual = _circular_import_counts()
    assert actual == CIRCULAR_IMPORT_ALLOWLIST, (
        "`# lazy: circular` workarounds drifted from the allowlist — a file "
        "missing here, an extra file, or a changed count means a cycle was "
        "added, fixed, or moved. Update CIRCULAR_IMPORT_ALLOWLIST in this "
        f"file to match, in the same diff, with a reason.\nactual={actual}\n"
        f"expected={CIRCULAR_IMPORT_ALLOWLIST}"
    )


# --- The behavioural half: does each module actually import on its own? -----
#
# The check above counts *workarounds*, so it is blind to a cycle carrying no
# workaround because import order happens to mask it. `zrb/__init__.py` masks
# exactly that: whichever subpackage it names first is fully loaded before the
# later lines reach the same modules by another route, so a loop between two of
# them never gets the chance to fail.
#
# A plain `import zrb.llm.ui` cannot expose it either — parent packages load
# before submodules, so `zrb/__init__.py` runs first and pre-warms
# `sys.modules` with the very modules under test. Stubbing the parents leaves
# the module's own import closure and nothing else, which is the thing whose
# self-sufficiency this asserts.


_ISOLATED_IMPORT = textwrap.dedent("""
    import importlib
    import pathlib
    import sys
    import types

    root = pathlib.Path(sys.argv[2]).resolve()
    sys.path.insert(0, str(root))
    target = sys.argv[1]
    parts = target.split(".")
    # Stub every parent package so its __init__ can't pre-warm sys.modules,
    # keeping __path__ intact so submodule resolution still works.
    for i in range(1, len(parts)):
        name = ".".join(parts[:i])
        module = types.ModuleType(name)
        module.__path__ = [str(root.joinpath(*parts[:i]))]
        sys.modules[name] = module
    importlib.import_module(target)
    """)


def _all_modules() -> list[str]:
    """Every target an ordinary `import zrb...` statement can name.

    Packages as well as plain modules: a package name imports its
    `__init__.py`, which a plain-module target never does — the subprocess
    stubs every parent, so importing `zrb.llm.agent.common` leaves
    `zrb/llm/agent/__init__.py` unexecuted. A barrel whose `__getattr__` or
    re-exports break is only caught by naming the package itself.

    The identifier-legal filter excludes the shipped skill tool scripts under
    `llm_plugin/*_skills/<skill>/tools/` — standalone CLI programs in
    hyphenated directories, which import nothing from `zrb`.
    """
    targets = set()
    for path in SRC.rglob("*.py"):
        relative = path.parent if path.name == "__init__.py" else path.with_suffix("")
        parts = relative.relative_to(SRC).parts
        if all(part.isidentifier() for part in parts):
            targets.add(".".join(("zrb", *parts)))
    targets.discard("zrb")
    return sorted(targets)


@pytest.mark.parametrize("module", _all_modules())
def test_every_module_imports_with_its_parents_stubbed(module: str):
    result = subprocess.run(
        [sys.executable, "-c", _ISOLATED_IMPORT, module, str(REPO_ROOT / "src")],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"`{module}` cannot be imported on its own — its import closure "
        "contains a cycle that is currently masked by whatever else loads "
        "first. Fix it at the source: trim the package __init__ re-export "
        "that drags a heavy sibling in, move a dependency-free leaf module out "
        "of the package it doesn't belong to, or — only when both directions "
        "are genuine — defer one import with a `# lazy: circular` tag and add "
        f"it to CIRCULAR_IMPORT_ALLOWLIST above.\n{result.stderr[-1500:]}"
    )
