"""The test tree mirrors `src/zrb`: a test sits beside the code it exercises.

"Mirrors" has two failures, and a green suite hides both — an import path is a
string, and pytest finds a test wherever it is put:

* a package whose tests still live one level up, in the directory of the
  package it was carved out of;
* a test file whose module lives one level down, so a reader looking for
  `test_file_read.py` starts in `test/llm/` and the file is somewhere else.

The two are the same defect from opposite ends, which is why both are checked.
A test named after a module is judged on its imports as well as its name: `web`
and `searxng` name a module in another package too, and `test/runner/test_web.py`
is about the web app, not `config/mixins/web.py`. A *descriptive* name
(`test_file_basics.py`) breaks no rule — it stays beside the package it
exercises, which the first rule already guarantees.
"""

import ast
import pathlib

REPO_ROOT = pathlib.Path(__file__).parents[2]
SRC = REPO_ROOT / "src" / "zrb"
TEST = REPO_ROOT / "test"

# Directories under `test/` with no `src/zrb` counterpart, and why each is not
# a mismatch: they are the repository's own fitness rules and scripts, which
# govern the tree rather than belonging to it. The last test fails when one of
# these gains a source directory, so the list cannot outlive its reasons.
TEST_ONLY_DIRS = {
    "architecture",  # fitness rules over the whole tree
    "scripts",  # the repository's own scripts, exercised as scripts
    "eval",  # the evaluation harness, which ships as a tool of its own
}

# Packages whose parts are asserted through a test in an enclosing directory
# rather than one of their own, and the test that does it. Verified below, so
# the exemption cannot rot: naming a test that does not import the package, or
# a package that gained a directory, fails.
COVERED_FROM_ABOVE = {
    # Five inert per-role defaults, assembled by `UIStateDefaultsMixin`: what
    # they must do is what the mixin and `MultiUI` assert of them.
    "llm/ui/fallback/defaults": "test/llm/ui/multi/test_multi_ui_defaults.py",
}

# Not code the package imports: a skill's companion scripts, shipped as files
# its reader runs by hand.
NOT_PACKAGE_CODE = ("llm_plugin/",)

# Packages with no test directory of their own, measured when this rule first
# ran. The list may only shrink — every line it loses is a package whose tests
# moved in beside it — and the last test fails on a line that was fixed or that
# no longer names a package. Most are page modules exercised through the route
# tests beside them; `config/mixins` is covered by `test/config/`'s setters.
KNOWN_UNMIRRORED = {
    "builtin/setup/latex",
    "config/mixins",
    "runner/web_route/chat_page",
    "runner/web_route/error_page",
    "runner/web_route/home_page",
    "runner/web_route/login_page",
    "runner/web_route/logout_page",
    "runner/web_route/node_page",
    "runner/web_route/node_page/group",
    "runner/web_route/node_page/task",
    "session_state_log",
}


def _src_packages() -> list[pathlib.Path]:
    """Every directory under `src/zrb` that holds a module a reader looks for."""
    return [
        path
        for path in SRC.rglob("*")
        if path.is_dir()
        and any(child.name != "__init__.py" for child in path.glob("*.py"))
        and not path.relative_to(SRC).as_posix().startswith(NOT_PACKAGE_CODE)
    ]


def _test_directories() -> list[pathlib.Path]:
    return sorted({path.parent for path in TEST.rglob("test_*.py")})


def _modules_by_stem() -> dict[str, list[pathlib.Path]]:
    found: dict[str, list[pathlib.Path]] = {}
    for module in SRC.rglob("*.py"):
        if module.name == "__init__.py":
            continue
        found.setdefault(module.stem, []).append(module)
    return found


def _dotted(module: pathlib.Path) -> str:
    return ".".join(module.relative_to(SRC.parent).with_suffix("").parts)


def _imports(path: pathlib.Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
        elif isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
    return names


def _imports_module(names: set[str], module: str) -> bool:
    return any(name == module or name.startswith(module + ".") for name in names)


def test_every_source_package_has_a_test_directory():
    missing = []
    for package in _src_packages():
        relative = package.relative_to(SRC).as_posix()
        if (TEST / relative).is_dir():
            continue
        if relative in COVERED_FROM_ABOVE or relative in KNOWN_UNMIRRORED:
            continue
        missing.append(relative)

    assert not missing, (
        "A package with modules but no test directory of its own: its tests "
        "still sit in the parent, so a reader looks one level too high. Move "
        f"them into test/<the same path>: {sorted(missing)}"
    )


def test_an_unmirrored_package_that_was_fixed_is_dropped_from_the_known_list():
    stale = sorted(
        name
        for name in KNOWN_UNMIRRORED
        if (TEST / name).is_dir() or not (SRC / name).is_dir()
    )

    assert not stale, (
        "These lines no longer describe a package without a test directory: "
        f"delete each one in the same diff: {stale}"
    )


def test_a_coverage_exemption_names_a_test_that_reaches_the_package():
    wrong = []
    for package, test in sorted(COVERED_FROM_ABOVE.items()):
        if (TEST / package).is_dir():
            wrong.append(f"{package}: has a test directory now — drop the exemption")
            continue
        path = REPO_ROOT / test
        if not path.is_file():
            wrong.append(f"{package}: {test} does not exist")
        elif not _imports_module(_imports(path), "zrb." + package.replace("/", ".")):
            wrong.append(f"{package}: {test} does not import it")

    assert not wrong, "Coverage exemptions that no longer hold: " + "; ".join(wrong)


def test_a_test_named_after_a_module_sits_beside_it():
    modules = _modules_by_stem()
    misplaced = []
    for test in sorted(TEST.rglob("test_*.py")):
        candidates = modules.get(test.stem[len("test_") :], [])
        # A descriptive name, or one several modules share and no path can
        # settle: the package rule above already covers where it belongs.
        if len(candidates) != 1:
            continue
        module = candidates[0]
        if module.parent == SRC / test.parent.relative_to(TEST):
            continue
        if not _imports_module(_imports(test), _dotted(module)):
            continue  # the name is a word two packages share
        misplaced.append(
            f"{test.relative_to(REPO_ROOT).as_posix()} names "
            f"{module.relative_to(REPO_ROOT).as_posix()}"
        )

    assert not misplaced, (
        "A test file is named after a module it imports, and sits in another "
        f"directory. Move each beside its module: {misplaced}"
    )


def test_a_test_directory_mirrors_a_source_directory():
    stray = sorted(
        directory.relative_to(TEST).as_posix()
        for directory in _test_directories()
        if directory.relative_to(TEST).as_posix() not in {"", *TEST_ONLY_DIRS}
        and not (SRC / directory.relative_to(TEST)).is_dir()
    )

    assert not stray, (
        "A test directory mirrors no source directory. Either it was renamed "
        "away from its package, or it belongs in TEST_ONLY_DIRS with the "
        f"reason written beside it: {stray}"
    )


def test_a_test_only_directory_that_gained_a_source_directory_is_dropped():
    stale = sorted(name for name in TEST_ONLY_DIRS if (SRC / name).is_dir())

    assert not stale, (
        "These directories are exempt from mirroring, and now have a source "
        f"directory to mirror. Move their tests and drop the exemption: {stale}"
    )
