"""ADR-0098's `-> bool` half, as a number that only goes down.

The ADR says a function annotated `-> bool` is named as a question -- `is_`,
`has_`, `should_`, `can_`, `needs_`, or an `_enabled`/`_active` suffix -- so
that `if task.is_cli_only:` reads as the check it is rather than as a value.
The annotation is the trigger, so there is nothing to judge per call site.

It was review vocabulary with no enforcement, and the tree drifted: most
`-> bool` functions do not follow it. A test that simply required the rule
would fail on day one and get deleted, so this pins the count instead. New
code cannot add to it, and every rename a passing file earns lowers it -- the
same shape as `test_complexity_ratchet.py` and the other ceilings here.

`BOOL_NAMES_NOT_PHRASED_AS_A_QUESTION` only ever goes DOWN. Lower it in the
same diff that renames something; never raise it to make a new function pass.
"""

import ast
import pathlib
import re

REPO_ROOT = pathlib.Path(__file__).parents[2]
SRC = REPO_ROOT / "src" / "zrb"

# ADR-0098's vocabulary exactly, plus a leading underscore so a private helper
# (`_is_in_windows_dir`) counts as phrased correctly.
_QUESTION = re.compile(r"^_?(is|has|should|can|needs)_|(_enabled|_active)$")

BOOL_NAMES_NOT_PHRASED_AS_A_QUESTION = 195


def _offenders() -> list[str]:
    """Every `-> bool` function in src/ whose name is not a question."""
    found: list[str] = []
    for path in sorted(SRC.rglob("*.py")):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:  # pragma: no cover - src/ always parses
            continue
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            # Dunders are named by the data model, not by us.
            if node.name.startswith("__"):
                continue
            returns = node.returns
            if not (isinstance(returns, ast.Name) and returns.id == "bool"):
                continue
            if not _QUESTION.search(node.name):
                found.append(f"{path.relative_to(SRC)}:{node.lineno} {node.name}")
    return found


def test_bool_naming_debt_does_not_grow():
    offenders = _offenders()
    assert len(offenders) <= BOOL_NAMES_NOT_PHRASED_AS_A_QUESTION, (
        f"{len(offenders)} `-> bool` functions are not named as a question, up "
        f"from {BOOL_NAMES_NOT_PHRASED_AS_A_QUESTION}. ADR-0098: name it "
        "`is_`/`has_`/`should_`/`can_`/`needs_`, or suffix a property "
        f"`_enabled`/`_active`. New: {sorted(offenders)[:10]}"
    )


def test_the_ratchet_is_tight():
    """A ceiling left above the real count silently re-opens the budget it
    was supposed to close, so a rename must lower the number in the same diff.
    """
    offenders = _offenders()
    assert len(offenders) == BOOL_NAMES_NOT_PHRASED_AS_A_QUESTION, (
        f"{BOOL_NAMES_NOT_PHRASED_AS_A_QUESTION - len(offenders)} `-> bool` "
        "name(s) were fixed without lowering the ratchet. Set "
        f"BOOL_NAMES_NOT_PHRASED_AS_A_QUESTION to {len(offenders)}."
    )
