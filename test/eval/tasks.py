"""The 15 evaluation tasks.

Each one is a small, self-contained repository state plus a request a user could
plausibly make. Checks run the result instead of reading it where they can:
importing the module or running the suite is what a user would do, and it
catches a plausible-looking edit that does not work.

The mix is deliberate — creation, a failing-test fix, a rename across files, a
deletion, restraint (one task fails if an unrelated file changes), and refactors.
Together they cover the mistakes an agent actually makes: not reading before
editing, leaving a stale reference, over-reaching, and reporting success on code
that does not run.
"""

from __future__ import annotations

import hashlib
import json

from harness import (
    EvalTask,
    read_text,
    run_pytest,
    run_python,
    sha256_text,
)

CALC_FIXTURE = """\
def add(a, b):
    return a - b
"""

CALC_TEST_FIXTURE = """\
from calc import add


def test_add():
    assert add(2, 3) == 5
"""

APP_FIXTURE = """\
def double(value):
    return value * 3
"""

UNTOUCHED_FIXTURE = """\
def untouched():
    return "do not touch"
"""


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _check_create_module(workspace):
    code, out, _ = run_python(workspace, "import hello; print(hello.greet('Ada'))")
    if code != 0:
        return "hello.greet('Ada') did not run"
    if out.strip() != "Hello, Ada!":
        return f"greet('Ada') returned {out.strip()!r}, expected 'Hello, Ada!'"
    return None


def _check_fix_failing_test(workspace):
    if sha256_text(workspace, "test_calc.py") != _digest(CALC_TEST_FIXTURE):
        return "the test file was modified; the task said to fix the code instead"
    code, report = run_pytest(workspace)
    if code != 0:
        return f"pytest still fails: {report.strip()[-300:]}"
    return None


def _check_add_function(workspace):
    code, out, err = run_python(
        workspace,
        "import mathops; print(mathops.add(2, 3), mathops.subtract(5, 3))",
    )
    if code != 0:
        return f"mathops did not import/run: {err.strip()[:200]}"
    if out.strip() != "5 2":
        return f"expected '5 2', got {out.strip()!r}"
    return None


def _check_rename_function(workspace):
    source = read_text(workspace, "app.py")
    if "process_data" in source:
        return "app.py still mentions process_data"
    if "transform_data" not in source:
        return "app.py does not define transform_data"
    code, out, _ = run_python(workspace, "import app; print(app.main())")
    if code != 0 or out.strip() != "['a', 'b']":
        return f"main() no longer behaves the same: {out.strip()!r}"
    return None


def _check_remove_dead_code(workspace):
    source = read_text(workspace, "helpers.py")
    if "unused_helper" in source:
        return "unused_helper is still in helpers.py"
    code, out, _ = run_python(workspace, "import helpers; print(helpers.used_helper(3))")
    if code != 0 or out.strip() != "6":
        return f"used_helper no longer works: {out.strip()!r}"
    return None


def _check_update_constant(workspace):
    code, out, err = run_python(
        workspace, "import config; print(config.TIMEOUT_SECONDS, config.RETRIES)"
    )
    if code != 0:
        return f"config did not import: {err.strip()[:200]}"
    if out.strip() != "60 3":
        return f"expected '60 3', got {out.strip()!r}"
    return None


def _check_add_test_for_function(workspace):
    source = read_text(workspace, "test_slugify.py")
    if not source:
        return "test_slugify.py was not created"
    if source.count("def test_") < 2:
        return "test_slugify.py has fewer than two tests"
    code, report = run_pytest(workspace)
    if code != 0:
        return f"pytest fails: {report.strip()[-300:]}"
    return None


def _check_fix_off_by_one(workspace):
    code, out, _ = run_python(workspace, "import counter; print(counter.count_to(3))")
    if code != 0:
        return "counter.count_to(3) did not run"
    if out.strip() != "[1, 2, 3]":
        return f"count_to(3) returned {out.strip()!r}"
    return None


def _check_json_edit(workspace):
    try:
        data = json.loads(read_text(workspace, "data.json"))
    except json.JSONDecodeError as error:
        return f"data.json is not valid JSON: {error}"
    if data.get("version") != "1.1.0":
        return f"version is {data.get('version')!r}, expected '1.1.0'"
    if data.get("name") != "demo" or data.get("dependencies") != {}:
        return "data.json changed more than the version"
    return None


def _check_readme_section(workspace):
    source = read_text(workspace, "README.md")
    if "## Usage" not in source:
        return "README.md has no '## Usage' heading"
    if "python demo.py" not in source:
        return "the Usage section does not mention `python demo.py`"
    if source.index("## Usage") < source.index("## Installation"):
        return "the Usage section is before Installation"
    return None


def _check_multi_file_constant(workspace):
    if "DEFAULT_NAME" in read_text(workspace, "settings.py"):
        return "settings.py still defines DEFAULT_NAME"
    if "DEFAULT_NAME" in read_text(workspace, "report.py"):
        return "report.py still imports DEFAULT_NAME"
    code, out, _ = run_python(workspace, "import report; print(report.title())")
    if code != 0 or out.strip() != "Report: demo":
        return f"report.title() broke: {out.strip()!r}"
    return None


def _check_fix_runtime_error(workspace):
    code, out, err = run_python(workspace, "exec(open('broken.py').read(), {'__name__': 'x'})")
    if code != 0:
        return f"broken.py still raises: {err.strip()[-200:]}"
    if "for value in (1, 2, 3)" not in read_text(workspace, "broken.py"):
        return "the loop was changed instead of the missing name"
    return None


def _check_refactor_extract(workspace):
    source = read_text(workspace, "report_text.py")
    if "def normalize(" not in source:
        return "report_text.py does not define normalize()"
    code, out, _ = run_python(
        workspace,
        "import report_text as r; "
        "print(r.header('  hello  world '), '|', r.footer('  HELLO  WORLD '))",
    )
    if code != 0:
        return "report_text did not import/run"
    if out.strip() != "HELLO WORLD | hello world":
        return f"behavior changed: {out.strip()!r}"
    return None


def _check_no_collateral_damage(workspace):
    if sha256_text(workspace, "untouched.py") != _digest(UNTOUCHED_FIXTURE):
        return "untouched.py changed; only app.py was in scope"
    code, out, _ = run_python(workspace, "import app; print(app.double(4))")
    if code != 0 or out.strip() != "8":
        return f"double(4) returned {out.strip()!r}, expected 8"
    return None


def _check_create_package(workspace):
    code, out, err = run_python(workspace, "import main; print(main.run())")
    if code != 0:
        return f"import main failed: {err.strip()[:200]}"
    if out.strip() != "HI!":
        return f"main.run() returned {out.strip()!r}, expected 'HI!'"
    return None


TASKS: tuple[EvalTask, ...] = (
    EvalTask(
        name="create_module",
        prompt=(
            "Create a file hello.py in the current directory defining greet(name), "
            "which returns 'Hello, {name}!'. Do not create anything else."
        ),
        files={},
        checks=(_check_create_module,),
    ),
    EvalTask(
        name="fix_failing_test",
        prompt=(
            "Running pytest in this directory fails. Fix the bug so the test passes. "
            "Do not modify the test file."
        ),
        files={"calc.py": CALC_FIXTURE, "test_calc.py": CALC_TEST_FIXTURE},
        checks=(_check_fix_failing_test,),
    ),
    EvalTask(
        name="add_function",
        prompt=(
            "Add a subtract(a, b) function to mathops.py that returns a - b, "
            "keeping the existing add function working."
        ),
        files={
            "mathops.py": (
                'def add(a, b):\n    """Return the sum of a and b."""\n    return a + b\n'
            )
        },
        checks=(_check_add_function,),
    ),
    EvalTask(
        name="rename_function",
        prompt=(
            "Rename process_data to transform_data everywhere in this project, "
            "keeping behavior identical."
        ),
        files={
            "app.py": (
                "def process_data(rows):\n"
                "    return [row.strip() for row in rows]\n"
                "\n"
                "\n"
                "def main():\n"
                '    return process_data([" a ", "b "])\n'
            )
        },
        checks=(_check_rename_function,),
    ),
    EvalTask(
        name="remove_dead_code",
        prompt=(
            "helpers.py has an unused_helper that nothing calls. Remove it and keep "
            "used_helper."
        ),
        files={
            "helpers.py": (
                "def used_helper(value):\n"
                "    return value * 2\n"
                "\n"
                "\n"
                "def unused_helper(value):\n"
                "    return value + 1\n"
            )
        },
        checks=(_check_remove_dead_code,),
    ),
    EvalTask(
        name="update_constant",
        prompt="Set TIMEOUT_SECONDS to 60 in config.py, leaving RETRIES alone.",
        files={"config.py": "TIMEOUT_SECONDS = 30\nRETRIES = 3\n"},
        checks=(_check_update_constant,),
    ),
    EvalTask(
        name="add_test_for_function",
        prompt=(
            "Add a test file test_slugify.py containing at least two tests for the "
            "existing slugify function."
        ),
        files={
            "slugify.py": (
                "def slugify(text):\n"
                '    return "-".join(text.lower().split())\n'
            )
        },
        checks=(_check_add_test_for_function,),
    ),
    EvalTask(
        name="fix_off_by_one",
        prompt="count_to(3) returns [1, 2] but it should return [1, 2, 3]. Fix it.",
        files={"counter.py": "def count_to(limit):\n    return list(range(1, limit))\n"},
        checks=(_check_fix_off_by_one,),
    ),
    EvalTask(
        name="json_edit",
        prompt="Bump the version in data.json to 1.1.0, changing nothing else.",
        files={
            "data.json": '{\n  "name": "demo",\n  "version": "1.0.0",\n'
            '  "dependencies": {}\n}\n'
        },
        checks=(_check_json_edit,),
    ),
    EvalTask(
        name="readme_section",
        prompt=(
            "Add a '## Usage' section to README.md explaining that the project runs "
            "with `python demo.py`, placed after the Installation section."
        ),
        files={
            "README.md": (
                "# Demo\n\nA tiny demo project.\n\n## Installation\n\npip install demo\n"
            )
        },
        checks=(_check_readme_section,),
    ),
    EvalTask(
        name="multi_file_constant",
        prompt=(
            "Rename DEFAULT_NAME to DEFAULT_LABEL in settings.py and update its "
            "import in report.py so both files still work."
        ),
        files={
            "settings.py": 'DEFAULT_NAME = "demo"\n',
            "report.py": (
                "from settings import DEFAULT_NAME\n"
                "\n"
                "\n"
                "def title():\n"
                '    return f"Report: {DEFAULT_NAME}"\n'
            ),
        },
        checks=(_check_multi_file_constant,),
    ),
    EvalTask(
        name="fix_runtime_error",
        prompt=(
            "Running broken.py raises NameError: name 'missing_offset' is not "
            "defined. Make it run and print 42, without rewriting the loop."
        ),
        files={
            "broken.py": (
                "def compute():\n"
                "    total = 0\n"
                "    for value in (1, 2, 3):\n"
                "        total += value\n"
                "    return total + missing_offset\n"
                "\n"
                "\n"
                'if __name__ == "__main__":\n'
                "    print(compute())\n"
            )
        },
        checks=(_check_fix_runtime_error,),
    ),
    EvalTask(
        name="refactor_extract",
        prompt=(
            "header() and footer() in report_text.py duplicate the same "
            "normalization. Extract it into a helper named normalize(text) in that "
            "file and use it in both. Behavior must not change."
        ),
        files={
            "report_text.py": (
                "def header(title):\n"
                '    return " ".join(title.strip().split()).upper()\n'
                "\n"
                "\n"
                "def footer(text):\n"
                '    return " ".join(text.strip().split()).lower()\n'
            )
        },
        checks=(_check_refactor_extract,),
    ),
    EvalTask(
        name="no_collateral_damage",
        prompt="double(4) returns 12 but it should return 8. Fix app.py.",
        files={"app.py": APP_FIXTURE, "untouched.py": UNTOUCHED_FIXTURE},
        checks=(_check_no_collateral_damage,),
    ),
    EvalTask(
        name="create_package",
        prompt=(
            "main.py imports toolkit.strings.shout, but that package does not exist "
            "yet. Create it so `import main` works and main.run() returns 'HI!', "
            "where shout(text) upper-cases the text and appends '!'."
        ),
        files={
            "main.py": (
                "from toolkit.strings import shout\n"
                "\n"
                "\n"
                "def run():\n"
                '    return shout("hi")\n'
            )
        },
        checks=(_check_create_package,),
    ),
)

TASKS_BY_NAME = {task.name: task for task in TASKS}
