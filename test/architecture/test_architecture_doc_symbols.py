"""Guards that every symbol an architecture page names is still real.

THE TRUTH CHECK. Every backticked `src/` or `test/` path must exist, a
`file.py::name` reference must name something defined in that file, and every
backticked identifier must still appear somewhere under `src/` or `test/`. A
rename that leaves a page stale fails here, so the cost of updating the page
falls on whoever made the rename.

`README.md` and `change-map.md` are exempt from the shape rules in
`test_architecture_docs.py`, but not from this one: their tables are the first
thing a maintainer opens, so a stale row costs more than a stale paragraph.

A sequence diagram's participants are the same promise in a different notation,
so they are checked here too. These rules live here rather than in the shape
guard because they are about what a name points at, not about where the section
puts it.
"""

import ast
import functools
import re
import tokenize
from pathlib import Path

from architecture_docs import REPO_ROOT, blocks, files, lifelines, name_of, ticked

_IDENT = re.compile(r"[A-Za-z_][\w.]*(?:\(\))?")
_WORD = re.compile(r"[^\w.]")

# The only labels allowed to name no symbol: the boundary of the system, where
# the reader is outside the codebase entirely.
_BOUNDARY = {"Caller", "User", "browser", "shell", "terminal", "client"}


@functools.cache
def _code_names() -> frozenset[str]:
    """Every name the code itself uses — never a word that survives only in prose.

    Read from the token stream, so comments and docstrings do not count: a
    renamed symbol whose old name lingers in a comment is still reported. A
    string literal counts only when it is a bare identifier, because that is
    how a name is registered rather than mentioned (`"DelegateToAgent"`, a
    `CFG` key, a patch target).
    """
    names: set[str] = set()
    for root in ("src", "test"):
        for path in (REPO_ROOT / root).rglob("*.py"):
            with path.open("rb") as source:
                for token in tokenize.tokenize(source.readline):
                    if token.type == tokenize.NAME:
                        names.add(token.string)
                    elif token.type == tokenize.STRING:
                        value = token.string.strip("rbuRBUfF").strip("\"'")
                        if re.fullmatch(r"[A-Za-z_]\w*", value):
                            names.add(value)
    return frozenset(names)


@functools.cache
def _defined_names() -> frozenset[str]:
    """Every name zrb defines for something a reader can go and open.

    Narrower than `_code_names`: a lifeline must be a thing, not any word the
    code happens to use, so a local variable named `config` does not count.
    Three sources, because a lifeline may legitimately be any of them:

    - a class or function defined under `src/`;
    - a name a module under `src/` imports by name, which is how third-party
      types such as `Tool` exist in zrb (`src/zrb/llm/agent/types.py`);
    - a name a tool is registered under (`"DelegateToAgent"`) — scoped to the
      tool package, so a stray quoted word elsewhere cannot bless a role-noun.
    """
    names: set[str] = set()
    for path in (REPO_ROOT / "src").rglob("*.py"):
        is_tool = "llm/tool" in path.as_posix()
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                names.add(node.name)
            elif isinstance(node, ast.ImportFrom):
                names |= {alias.asname or alias.name for alias in node.names}
            elif (
                is_tool
                and isinstance(node, ast.Constant)
                and isinstance(node.value, str)
                and re.fullmatch(r"[A-Za-z_]\w*", node.value)
            ):
                names.add(node.value)
    return frozenset(names)


def _defines(tree: ast.Module, dotted: list[str]) -> bool:
    """Whether `Class.method` (or a bare name) is defined at that nesting in the module."""
    body: list[ast.stmt] = tree.body
    for part in dotted:
        found = next(
            (
                node
                for node in body
                if isinstance(
                    node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
                )
                and node.name == part
            ),
            None,
        )
        if found is None:
            return False
        body = found.body
    return True


def test_every_named_path_exists():
    """A path the reader cannot open is a broken promise.

    `file.py::name` must be defined in that file. Nesting is written either
    way pytest and Python write it: `test_x.py::TestClass::test_y` or
    `module.py::Class.method`.
    """
    offenders = []
    for path in files():
        for token in ticked(path):
            if not token.startswith(("src/", "test/")) or re.search(r"[{*<\s]", token):
                continue
            file_part, _, name = token.partition("::")
            target = REPO_ROOT / file_part.rstrip("/")
            if not target.exists():
                offenders.append(f"{name_of(path)}: `{token}` (no such path)")
                continue
            if name:
                dotted = re.split(r"::|\.", name)
                tree = ast.parse(target.read_text(encoding="utf-8"))
                if not _defines(tree, dotted):
                    offenders.append(f"{name_of(path)}: `{token}` (no {name} there)")
    assert not offenders, (
        "Page(s) naming a path or test that does not exist. Update the page "
        f"to the new location: {offenders}"
    )


def test_every_named_identifier_still_exists():
    """A renamed symbol leaves its old name nowhere in the code; the page must follow."""
    words = _code_names()
    offenders = []
    for path in files():
        for token in set(ticked(path)):
            if not _IDENT.fullmatch(token):
                continue
            name = token.removesuffix("()")
            # A file name (`AGENTS.md`) is not an identifier.
            if re.search(r"\.(?:md|py|toml|json|ya?ml|txt|sh)$", name):
                continue
            # Plain words (`Shell`, `READ`) cannot be told apart from English;
            # only names shaped like code are checked.
            if (
                "_" not in name
                and "." not in name
                and not re.search(r"[a-z][A-Z]", name)
            ):
                continue
            missing = [part for part in name.split(".") if part and part not in words]
            if missing:
                offenders.append(f"{path.name}: `{token}`")
    assert not offenders, (
        "Page(s) naming an identifier that no longer appears in the code under "
        f"src/ or test/ (comments and docstrings do not count). It was renamed or removed; update the page: {offenders}"
    )


def test_every_lifeline_names_a_real_symbol():
    """A lifeline is an object or callable, not a role-noun or a value type."""
    symbols = _defined_names()
    words = _code_names()
    offenders = []
    for path in files():
        for line, source in blocks(path):
            for label in lifelines(source):
                if label in _BOUNDARY:
                    continue
                # A qualified third-party symbol (`pydantic_ai.Agent`) is fine
                # when zrb's code uses every part of it; a bare `Agent` is not,
                # because the reader cannot tell whose.
                if "." in label:
                    if all(part in words for part in label.split(".")):
                        continue
                    offenders.append(
                        f"{name_of(path)}:{line} {label!r}"
                    )
                    continue
                # The label leads with the symbol; a trailing qualifier names
                # which instance it is (`BaseTask root`). Leading with a role
                # word is what makes a lifeline unopenable, so only the first
                # word is checked — otherwise `child UI` passes on `UI`.
                head = _WORD.sub("", label.split()[0])
                if head in symbols:
                    continue
                offenders.append(f"{name_of(path)}:{line} {label!r}")
    assert not offenders, (
        "Lifeline(s) that name no real symbol. A participant must be a class or "
        "callable defined under src/ (a trailing instance qualifier is fine, so "
        "`BaseTask root` passes), or a third-party symbol qualified with its "
        f"module (`pydantic_ai.Agent`): {offenders}"
    )
