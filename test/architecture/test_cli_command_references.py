"""Guards against CLI command strings in `src/` going stale.

Moving a task to a different group silently invalidates every message and
docstring that spells out its old path — the prose still reads fine, and
following it lands the user on "Invalid subcommand". `test_doc_code_references`
does this for file paths in `docs/`; this does it for command paths in code.

A command is resolved against the real group tree, so an alias, a nested
group, and a top-level alias all pass on their own terms. `{CFG.ROOT_GROUP_NAME}`
counts as the root: a runtime message should interpolate it rather than
hardcode `zrb`, since the root group is renameable.
"""

import ast
import re
from pathlib import Path

from zrb.config.config import CFG
from zrb.runner.cli import cli

SRC = Path(__file__).parents[2] / "src" / "zrb"

# Path relative to src/zrb -> commands that name user-defined tasks in an
# illustrative example, not builtins. An entry means "this is prose about a
# task the reader writes", not "this is allowed to be wrong".
COMMAND_EXCEPTIONS: dict[str, set[str]] = {
    "group/group.py": {"db migrate", "test", "lint"},
}

_COMMAND = re.compile(
    r"`(?:\{CFG\.ROOT_GROUP_NAME\}|\{self\.ROOT_GROUP_NAME\}|"
    + re.escape(CFG.ROOT_GROUP_NAME)
    + r")((?: [a-z][a-z0-9-]*)+)`"
)


def _resolves(parts: list[str]) -> bool:
    node = cli
    for index, segment in enumerate(parts):
        group = node.get_group_by_alias(segment)
        if group is not None:
            node = group
            continue
        if node.get_task_by_alias(segment) is not None:
            # A task ends the path; nothing can be nested under it.
            return index == len(parts) - 1
        return False
    return True


def _strings_in(tree: ast.Module):
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            yield node.lineno, node.value
        elif isinstance(node, ast.JoinedStr):
            yield node.lineno, "".join(
                (
                    part.value
                    if isinstance(part, ast.Constant)
                    else "{" + ast.unparse(part.value) + "}"
                )
                for part in node.values
                if isinstance(part, (ast.Constant, ast.FormattedValue))
            )


def test_cli_command_strings_resolve_against_the_real_group_tree():
    stale = []
    for path in sorted(SRC.rglob("*.py")):
        rel = path.relative_to(SRC).as_posix()
        allowed = COMMAND_EXCEPTIONS.get(rel, set())
        for lineno, text in _strings_in(ast.parse(path.read_text(encoding="utf-8"))):
            for match in _COMMAND.finditer(text):
                command = " ".join(match.group(1).split())
                if command in allowed or _resolves(command.split()):
                    continue
                stale.append(f"{rel}:{lineno}: `{CFG.ROOT_GROUP_NAME} {command}`")
    assert not stale, (
        "CLI command string(s) that no longer resolve — the task moved, or the "
        "command names a user-defined task and belongs in COMMAND_EXCEPTIONS:\n"
        + "\n".join(stale)
    )
