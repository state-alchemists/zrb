"""One reader for the run's column.

`stream_indentation` decides where a run's prose lands on screen. Reading it in
more than one place is how the transcript grew paths that render at the margin:
each reader re-decides the rule — narrow the render by the column, then prefix
every non-blank line — and one of them eventually keeps half of it. The column
is read in `_render_at_column` and nowhere else, so a new entry point goes
through the funnel instead of around it.

The count is one, deliberately: unlike a ratchet over writers (which is dozens
of legitimate lines and gets rubber-stamped), a second reader is always a bug.
"""

import ast
import pathlib

REPO_ROOT = pathlib.Path(__file__).parents[2]
SRC = REPO_ROOT / "src" / "zrb"

COLUMN_ATTRIBUTE = "stream_indentation"
SOLE_READER = "_render_at_column"


def _functions_reading_column() -> set[str]:
    """Every function that reads the attribute — a load, not a write."""
    readers: set[str] = set()
    for path in sorted(SRC.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for function in ast.walk(tree):
            if not isinstance(function, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for node in ast.walk(function):
                is_read = (
                    isinstance(node, ast.Attribute)
                    and node.attr == COLUMN_ATTRIBUTE
                    and isinstance(node.ctx, ast.Load)
                )
                if is_read:
                    readers.add(function.name)
    return readers


def test_the_column_is_read_in_exactly_one_function():
    readers = _functions_reading_column()
    assert readers == {SOLE_READER}, (
        "The run's column must be read in "
        f"`{SOLE_READER}` alone; read in {sorted(readers)}. A second reader "
        "re-decides the layout rule — render narrow, then prefix — and one of "
        "the two will eventually forget half of it."
    )
