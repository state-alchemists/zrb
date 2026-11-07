"""Guards the `zrb` imports a live doc shows from going stale.

A doc's code sample is a promise: a reader copies it. Moving a class — as this
refactor does, package after package — leaves the sample importing a name that no
longer exists, and nothing catches it, because the prose guard
(`test_doc_code_references.py`) only resolves `src/...` *paths* and links, and a
changelog is exempt as frozen history.

Only `zrb` imports are checked. A sample's `import discord`, `import telebot` or
`import websockets` is the reader's dependency, not this repository's to keep
current, so it is left alone. Changelogs are skipped for the same reason they are
skipped there: they are the record of what was true at the time.
"""

import importlib
import re
from pathlib import Path

REPO_ROOT = Path(__file__).parents[2]

_FENCE = re.compile(r"^\s*```(\w*)\s*$")
# `from zrb.x import a, b` (possibly indented, inside a function body) and
# `import zrb.x`. A trailing comment is dropped before the name list is split.
_FROM_IMPORT = re.compile(r"^\s*from\s+(zrb[\w.]*)\s+import\s+(.+)$")
_IMPORT = re.compile(r"^\s*import\s+(zrb[\w.]*)")


def _live_docs() -> list[Path]:
    """Every markdown file a reader is expected to follow, minus frozen history."""
    docs = [p for p in (REPO_ROOT / "docs").rglob("*.md") if "changelog" not in p.parts]
    examples = sorted((REPO_ROOT / "examples").rglob("README.md"))
    return [REPO_ROOT / "AGENTS.md", REPO_ROOT / "README.md", *sorted(docs), *examples]


def _python_fences(text: str) -> list[list[str]]:
    """The lines of every fenced block that holds Python.

    An unmarked fence counts as Python: most of the short samples in this tree are
    written without an info string. A fence marked in another language is skipped
    whole — reading its body as a sample would turn `from zrb.nope import x` in a
    shell transcript into a finding.
    """
    fences: list[list[str]] = []
    body: list[str] | None = None
    skipping = False
    for line in text.splitlines():
        stripped = line.strip()
        if skipping:
            skipping = not stripped.startswith("```")
            continue
        if body is not None:
            if stripped.startswith("```"):
                fences.append(body)
                body = None
            else:
                body.append(line)
            continue
        match = _FENCE.match(line)
        if not match:
            continue
        if match.group(1) in ("", "python", "py"):
            body = []
        else:
            skipping = True
    if body:
        fences.append(body)
    return fences


def _zrb_imports(lines: list[str]) -> list[tuple[str, list[str]]]:
    """(module, names) for each `zrb` import in a fence; names may be empty."""
    found: list[tuple[str, list[str]]] = []
    for line in lines:
        match = _FROM_IMPORT.match(line)
        if match:
            module, names = match.group(1), match.group(2).split("#")[0]
            found.append(
                (module, [name.strip() for name in names.split(",") if name.strip()])
            )
            continue
        match = _IMPORT.match(line)
        if match:
            found.append((match.group(1), []))
    return found


def test_every_zrb_import_in_a_live_doc_resolves():
    """A moved class must not leave a sample importing it from where it was.

    The failure a reader pays for is a copied sample raising `ImportError`, and
    the fix is one line in the doc — but only a check that imports the module and
    reads the attribute finds it before the reader does.
    """
    broken = []
    for doc in _live_docs():
        for fence in _python_fences(doc.read_text(encoding="utf-8")):
            for module, names in _zrb_imports(fence):
                try:
                    imported = importlib.import_module(module)
                except Exception as exc:  # noqa: BLE001 -- any failure is the finding
                    broken.append(
                        f"{doc.name}: import {module} -> {type(exc).__name__}"
                    )
                    continue
                for name in names:
                    if name == "*" or not name.isidentifier():
                        continue
                    if not hasattr(imported, name):
                        broken.append(
                            f"{doc.name}: from {module} import {name} -> gone"
                        )
    assert not broken, "live doc samples import names zrb no longer has: " + "; ".join(
        sorted(set(broken))
    )


def test_the_guard_reads_python_fences_and_judges_only_zrb():
    """A fence in another language is not Python, and a third-party import is the
    reader's own dependency; treating either as ours would report a false
    positive, and a guard that cries wolf gets deleted."""
    text = (
        "```python\nfrom zrb.llm.ui import AnyUI\n```\n"
        "```python\nfrom zrb.llm.ui import NotAThing\n```\n"
        "```bash\nfrom zrb.nope import nothing\n```\n"
        "```python\nimport discord\n```\n"
        "```\nfrom zrb.llm.ui import BaseUI\n```\n"
    )
    fences = _python_fences(text)
    assert [_zrb_imports(fence) for fence in fences] == [
        [("zrb.llm.ui", ["AnyUI"])],
        [("zrb.llm.ui", ["NotAThing"])],
        # `import discord` is a Python fence with no zrb import in it; the shell
        # fence above never became one, which is why there are four and not five.
        [],
        [("zrb.llm.ui", ["BaseUI"])],
    ]
