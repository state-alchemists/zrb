"""Guards live docs and examples against the one templating mistake that reads as working code.

`Tpl` is opt-in: a plain `str` is a literal and is never rendered
(`util/attr.py::get_attr`, ADR-0005). So `cmd="echo {ctx.input.who}"` echoes the
braces, and a `LLMTask(message="read {ctx.input.dir}")` sends the model the text
`{ctx.input.dir}` instead of a path. Neither raises: the task renders, exits 0,
and is simply wrong.

`README.md`'s "let the agent draw your codebase" example carried exactly this,
in the one block a new user is most likely to copy, while every file under
`examples/` had it right — including `examples/cmd-task/zrb_init.py`, whose
comment spells the rule out. Nothing executed the README, so nothing could say
so; this does not execute it either, it reads it.

The rule is not "no placeholder in a plain string" but "a placeholder has to
reach something that renders it". Two things do: `Tpl(...)`, the marker that
asks for rendering, and an explicit `ctx.render(...)` call, which is the
documented way to render on demand (`docs/core-concepts/session-and-context.md`).
A literal handed to either is correct and is not reported.

Two sources are read, because they are the two places a user copies code from:
every `.py` under `examples/`, and the python-fenced blocks of `README.md` and
the live `docs/` tree. A fence that does not parse is skipped — docs legitimately
show fragments (`...`, a bare expression, a signature list) that are not modules,
and 197 of the 207 python fences parse today.

Changelogs are excluded for the same reason `test_doc_code_references.py`
excludes them: they are frozen history, correct as a record of what the code did
at the time.
"""

import ast
import re
from pathlib import Path

REPO_ROOT = Path(__file__).parents[2]

# The placeholder syntax `Tpl` renders.
_PLACEHOLDER = re.compile(r"\{ctx\.")

# A python-fenced block in Markdown. Only python fences: the bash ones are
# shell, and a bash sample cannot be missing `Tpl`.
_PY_FENCE = re.compile(r"```python\n(.*?)```", re.DOTALL)

# The renderers: the `Tpl` marker, and the `ctx.render(...)` method, which
# renders on demand whatever its receiver is.
_MARKER = "Tpl"
_RENDER_METHOD = "render"

# A floor on how many samples the scan must reach, so a fence regex that stops
# matching (a doc reformatted to `~~~python`, a CRLF checkout) fails here rather
# than leaving every doc unchecked behind a green suite. The real count today is
# 21 example modules + 207 fences.
_MINIMUM_SAMPLES = 200

# (repo-relative path, line of the block) -> why the sample is correct as
# written. Line-keyed on purpose: editing above an exception shifts it and this
# test then reports the block it was written for, rather than silently excusing
# whichever block moved into that line.
PLACEHOLDER_EXCEPTIONS: dict[str, set[int]] = {}


def _example_files() -> list[Path]:
    return sorted((REPO_ROOT / "examples").rglob("*.py"))


def _live_docs() -> list[Path]:
    docs = [p for p in (REPO_ROOT / "docs").rglob("*.md") if "changelog" not in p.parts]
    return [REPO_ROOT / "README.md", *sorted(docs)]


def _is_renderer(call: ast.Call) -> bool:
    return (isinstance(call.func, ast.Name) and call.func.id == _MARKER) or (
        isinstance(call.func, ast.Attribute) and call.func.attr == _RENDER_METHOD
    )


def _rendered_values(tree: ast.AST) -> set[int]:
    """Ids of every node handed to a renderer, and so rendered rather than literal."""
    rendered: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and _is_renderer(node):
            rendered.update(id(argument) for argument in node.args)
            rendered.update(id(keyword.value) for keyword in node.keywords)
    return rendered


def _offending_literals(source: str, first_line: int) -> list[tuple[int, str]]:
    """Every placeholder string that never reaches a renderer, as `(line, text)`.

    `first_line` is where `source` starts in its file, so a node's line inside a
    fenced block maps back to a line a reader can find.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []  # a doc fragment, not a module
    rendered = _rendered_values(tree)
    offenders = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
            continue
        # An f-string is a JoinedStr, not a Constant, so it is out of scope: it
        # fails loudly at run time rather than rendering as literal text.
        if id(node) in rendered or not _PLACEHOLDER.search(node.value):
            continue
        offenders.append((first_line + node.lineno - 1, node.value[:60]))
    return offenders


def _code_samples() -> list[tuple[Path, int, str]]:
    """Every Python sample a user may copy, as `(path, first line, source)`."""
    samples = [(path, 1, path.read_text(encoding="utf-8")) for path in _example_files()]
    for path in _live_docs():
        text = path.read_text(encoding="utf-8")
        for fence in _PY_FENCE.finditer(text):
            first_line = text[: fence.start(1)].count("\n") + 1
            samples.append((path, first_line, fence.group(1)))
    return samples


def _findings() -> list[str]:
    found = []
    for path, first_line, source in _code_samples():
        relative_path = path.relative_to(REPO_ROOT).as_posix()
        exempt = PLACEHOLDER_EXCEPTIONS.get(relative_path, set())
        for line, text in _offending_literals(source, first_line):
            if line not in exempt:
                found.append(f"{relative_path}:{line} {text!r}")
    return found


def test_no_code_sample_passes_a_placeholder_to_a_literal_attribute():
    findings = _findings()
    assert not findings, (
        "Code sample(s) put a `{ctx.` placeholder in a plain string that never "
        "reaches a renderer, so the reader is handed the text `{ctx...}` instead "
        "of the value it names. Wrap it in `Tpl(...)`; "
        "`examples/agent-in-pipeline/zrb_init.py` is the shape to copy: {findings}"
    )


def test_the_scan_reaches_the_docs_and_examples_it_guards():
    samples = _code_samples()
    assert len(samples) >= _MINIMUM_SAMPLES, (
        f"only {len(samples)} code samples reached, under the {_MINIMUM_SAMPLES} "
        "expected. The fence regex has probably stopped matching, which leaves "
        "every doc unchecked while this file stays green."
    )


def test_the_check_reports_the_readme_block_it_was_written_for():
    """The regression itself: the README's `message=` as it stood before this test.

    Pinned literally rather than as a paraphrase, because the whole difficulty is
    that the wrong version is indistinguishable from the right one by eye.
    """
    before = 'from zrb import LLMTask\n\nLLMTask(\n    name="m",\n    message=(\n        "Read {ctx.input.dir}"\n    ),\n)\n'
    assert _offending_literals(before, 1) == [(6, "Read {ctx.input.dir}")]

    after = 'from zrb import LLMTask, Tpl\n\nLLMTask(\n    name="m",\n    message=Tpl(\n        "Read {ctx.input.dir}"\n    ),\n)\n'
    assert _offending_literals(after, 1) == []


def test_the_check_leaves_an_explicit_render_call_alone():
    """`ctx.render(...)` is the documented way to render on demand.

    Reporting it would make this test wrong about correct documentation, which is
    how a guard gets deleted instead of obeyed.
    """
    source = 'from zrb import make_task\n\nmake_task(name="t")\ndef t(ctx):\n    return ctx.render("Hello {ctx.input.user}!")\n'
    assert _offending_literals(source, 1) == []


def test_the_check_is_not_satisfied_by_marking_every_literal_rendered():
    """A `_rendered_values` that returned every id would pass the guard vacuously."""
    literal = 'from zrb import Tpl\ncmd = "echo {ctx.input.who}"\nmessage = Tpl("{ctx.input.dir}")\n'
    assert _offending_literals(literal, 1) == [(2, "echo {ctx.input.who}")]

    # A keyword the renderer wraps counts too — `Callback(input_mapping=...)`.
    nested = 'from zrb import Callback, Tpl\ncb = Callback(input_mapping={"m": Tpl("{ctx.x}")})\n'
    assert _offending_literals(nested, 1) == []
