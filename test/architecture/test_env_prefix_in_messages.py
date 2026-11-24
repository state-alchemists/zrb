"""A message a user reads names their own environment prefix, never `ZRB_`.

zrb is white-labelled: `CFG.ENV_PREFIX` renames every setting and the variable
that sets it. A message that spells the default prefix is wrong for every
deployment that renamed it, and it is wrong in the worst way — the user follows
it, sets a variable nothing reads, and the setting stays as it was.

The scan is over string constants, so a comment may spell the default while
explaining this rule. The two bare bootstrap keys (`_ZRB_ENV_PREFIX`,
`_ZRB_CUSTOM_VERSION`) carry a leading underscore, because they must be readable
before the prefix can be known, and they do not match the pattern.
"""

import ast
import re
from pathlib import Path

REPO_ROOT = Path(__file__).parents[2]
SRC = REPO_ROOT / "src" / "zrb"

_HARDCODED_PREFIX = re.compile(r"\bZRB_[A-Z]")


def _offenders() -> list[str]:
    found: list[str] = []
    for path in sorted(SRC.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
                continue
            match = _HARDCODED_PREFIX.search(node.value)
            if match:
                where = path.relative_to(REPO_ROOT)
                found.append(f"{where}:{node.lineno}: {match.group()}")
    return found


def test_no_message_hardcodes_the_default_prefix():
    offenders = _offenders()
    assert not offenders, (
        "These strings name the default prefix, which a white label renames: "
        f'{offenders}. Use f"{{CFG.ENV_PREFIX}}_..." at the point the message '
        "is built, so the read stays lazy."
    )
