"""Locks in three conventions AGENTS.md documents but nothing previously
enforced mechanically, repo-wide:

1. A part reaches its owner or a sibling only through a public property or
   method — never a raw `_private` attribute on another object (AGENTS.md's
   part-boundary rule).
2. Business logic (everything outside the presentation layer) stays free of
   web/TUI framework imports — `llm/ui`, `llm/app`, `runner`, and `input` are
   the presentation layer and are exempt; everything else (task engine, LLM
   agent/tool/permission/history/hook machinery, builtins, ...) is consumed
   by both the CLI and the web runner, so it cannot depend on either's
   framework.
3. Every extension point (an ABC or Protocol a user implements to plug into
   zrb) is `Any<Thing>` in `any_<thing>.py` — R9. `AnyTask`, `AnyInput`,
   `AnyUI`, `AnyApprovalChannel`, ... are the pattern; a capability-check
   Protocol used only for a local `isinstance` probe, or a callback-signature
   Protocol, is not an extension point (see `EXTENSION_POINT_EXCEPTIONS` and
   `_is_callable_only_protocol`).
4. No bare `raise Exception(...)` — R10. It tells a caller nothing and
   cannot be caught selectively; every raise site names a real exception
   type.
5. No constant-string error message under 40 characters — R10. A message
   that short cannot name the setting, the bad value, and the remedy. An
   f-string or a variable is assumed to carry that context already, so only
   bare `ast.Constant` string literals are checked.
6. Every sibling class in `config/mixins/` ends in `Mixin` — R11. One
   naming convention per package; AGENTS.md's rule that `Mixin` means
   reusable is the reason it's `Mixin`, not `Config<Thing>`.

Verified clean against the whole tree before being turned into a test: rule 1
trips on exactly 3 legitimate patterns (`super()` delegation, the singleton
`__new__` pattern that stashes state directly on `cls`, and one third-party
monkeypatch in `llm/agent/run/openai_patch.py`), each handled below instead of
suppressed by a growing per-file allowlist. If a genuinely new exception shows
up, extend `_PrivateAccessVisitor` or `MONKEYPATCH_EXCEPTIONS` — don't widen
the private-name check itself, that's the whole point of the rule.
"""

import ast
import re
from pathlib import Path

REPO_ROOT = Path(__file__).parents[2]
SRC = REPO_ROOT / "src" / "zrb"

# One-off, by-name exceptions to rule 1 — see the module docstring. Keep this
# short; if it grows, the visitor's pattern-matching is the better fix.
MONKEYPATCH_EXCEPTIONS = {
    "src/zrb/llm/agent/run/openai_patch.py",
}

# Directories that ARE the presentation layer, exempt from rule 2.
FRAMEWORK_EXEMPT_DIRS = ("llm/ui", "llm/app", "runner", "input")
FORBIDDEN_IMPORT_PREFIXES = ("fastapi", "starlette", "prompt_toolkit")

# One-off, by-name exceptions to rule 3 (R9) — see
# test_every_extension_point_is_named_any_thing_in_any_thing_py's docstring.
# Each is a @runtime_checkable Protocol used for a local isinstance-based
# capability check on an ad-hoc object, never exposed as a settable/
# constructor slot type on any public object — the "structural annotation,
# not an extension point" case the ratchet's own design doc calls out. Keep
# this short; if it grows past three, the rule is wrong, not the exemptions.
EXTENSION_POINT_EXCEPTIONS = {
    # apply_common_tools's minimal duck-typed host requirement — no public
    # object exposes a "host: CommonToolHost" slot.
    "CommonToolHost",
    # llm/agent/spill.py's payload store — only LocalFileStore implements it
    # today, and default_spill_store is a hardcoded module singleton with no
    # public way to swap it yet (dead extensibility, like the old
    # LLMConfig.model_settings Phase 6 found and deleted).
    "OverflowStore",
    # run_agent_task's isinstance check for "can this UI feed the activity
    # panel" — a capability probe, not a slot any task/UI constructor takes.
    "HasActivityTracking",
}


def _iter_py_files():
    yield from SRC.rglob("*.py")


class _PrivateAccessVisitor(ast.NodeVisitor):
    """Flags `obj.attr` where `attr` is private and `obj` isn't `self`/`cls`,
    except:

    - `super().foo` — base-class delegation, not a sibling reach.
    - `cls._instance.foo` inside `__new__` — the singleton pattern stashing
      state on the not-yet-returned instance, which IS `self` in disguise.
    """

    def __init__(self) -> None:
        self.violations: list[tuple[int, str]] = []
        self._function_stack: list[str] = []

    def visit_FunctionDef(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        self._function_stack.append(node.name)
        self.generic_visit(node)
        self._function_stack.pop()

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_Attribute(self, node: ast.Attribute) -> None:
        self.generic_visit(node)
        if not node.attr.startswith("_") or node.attr.startswith("__"):
            return
        value = node.value
        if isinstance(value, ast.Name) and value.id in ("self", "cls"):
            return
        if (
            isinstance(value, ast.Call)
            and isinstance(value.func, ast.Name)
            and value.func.id == "super"
        ):
            return
        if (
            self._function_stack
            and self._function_stack[-1] == "__new__"
            and isinstance(value, ast.Attribute)
            and value.attr == "_instance"
            and isinstance(value.value, ast.Name)
            and value.value.id == "cls"
        ):
            return
        self.violations.append((node.lineno, node.attr))


def _private_cross_accesses(tree: ast.AST) -> list[tuple[int, str]]:
    visitor = _PrivateAccessVisitor()
    visitor.visit(tree)
    return visitor.violations


def _forbidden_import(tree: ast.AST) -> str | None:
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith(FORBIDDEN_IMPORT_PREFIXES):
                    return alias.name
        elif isinstance(node, ast.ImportFrom) and node.module:
            if node.module.startswith(FORBIDDEN_IMPORT_PREFIXES):
                return node.module
    return None


def test_no_part_reaches_another_objects_private_state():
    """A part reaches owner/sibling state via `self._llm_task.tools` (public),
    never `self._llm_task._tools` (private) — see AGENTS.md's "Mixin means
    reusable" section, the paragraph on how a part reaches what it needs.
    """
    offenders = {}
    for path in _iter_py_files():
        rel = str(path.relative_to(REPO_ROOT))
        if rel in MONKEYPATCH_EXCEPTIONS:
            continue
        tree = ast.parse(path.read_text(), filename=str(path))
        violations = _private_cross_accesses(tree)
        if violations:
            offenders[rel] = violations
    assert not offenders, (
        "Found a private attribute reached through another object — only "
        f"same-object access (via `self` or `cls`) is allowed: {offenders}"
    )


def test_business_logic_stays_free_of_presentation_frameworks():
    """fastapi/starlette belong to `runner/`; prompt_toolkit belongs to
    `llm/ui/` and `llm/app/` (and `input/`, for its own CLI prompting) — not
    the engine, agent, tool, or permission code both the CLI and the web
    runner drive.
    """
    offenders = {}
    for path in _iter_py_files():
        rel = str(path.relative_to(SRC))
        if rel.startswith(FRAMEWORK_EXEMPT_DIRS):
            continue
        tree = ast.parse(path.read_text(), filename=str(path))
        found = _forbidden_import(tree)
        if found:
            offenders[rel] = found
    assert not offenders, f"Framework import found in business logic: {offenders}"


def _base_name(node: ast.expr) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _is_extension_point(node: ast.ClassDef) -> bool:
    """An ABC or a `Protocol`, by direct base name (or `metaclass=ABCMeta`).

    Syntactic, not semantic: it does not resolve imports or walk the MRO, so
    a class that is *transitively* an ABC through a non-ABC-named parent
    (`AnyContext(AnySharedContext)`) is not caught here — matching the scope
    of this check everywhere else in the file (single-file AST parse, no
    cross-module resolution).
    """
    for base in node.bases:
        if _base_name(base) in ("ABC", "Protocol"):
            return True
    return any(
        kw.arg == "metaclass" and _base_name(kw.value) == "ABCMeta"
        for kw in node.keywords
    )


def _is_callable_only_protocol(node: ast.ClassDef) -> bool:
    """A `Protocol` whose only member is `__call__` types a function
    signature (a callback shape), not an object with swappable behavior —
    the plan's "file-like or callback signature" exemption case, encoded as
    a rule rather than a per-name exception since any future callback
    Protocol is the same shape."""
    methods = [
        n.name
        for n in node.body
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]
    return methods == ["__call__"]


def _snake(name: str) -> str:
    s1 = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", name)
    return re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s1).lower()


def test_every_extension_point_is_named_any_thing_in_any_thing_py():
    """R9. An ABC/Protocol that names a slot on a public object — the thing a
    user implements to plug into zrb — is `Any<Thing>` in `any_<thing>.py`,
    matching `AnyTask`, `AnyInput`, `AnyUI`, `AnyApprovalChannel`, etc. Two
    kinds of Protocol are not extension points and are excluded rather than
    flagged: a callback-signature Protocol (`_is_callable_only_protocol`) and
    the three named, commented cases in `EXTENSION_POINT_EXCEPTIONS`.
    """
    offenders = []
    for path in _iter_py_files():
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef) or not _is_extension_point(node):
                continue
            if (
                _is_callable_only_protocol(node)
                or node.name in EXTENSION_POINT_EXCEPTIONS
            ):
                continue
            expected_file = f"any_{_snake(node.name.removeprefix('Any'))}.py"
            if not node.name.startswith("Any") or path.name != expected_file:
                offenders.append(f"{path.relative_to(SRC)}:{node.lineno} {node.name}")
    assert not offenders, (
        "Extension point(s) not named Any<Thing> in any_<thing>.py (R9): "
        f"{offenders}"
    )


# Exemptions for rule 5 (message length) — see
# test_no_error_message_is_shorter_than_forty_characters's docstring. Empty
# on purpose: every current offender was fixed rather than exempted (R10).
# Keep this short; a growing list means the threshold, not the rule, is wrong.
SHORT_MESSAGE_EXCEPTIONS: dict[str, set[int]] = {}


def _iter_raises(tree: ast.AST):
    for node in ast.walk(tree):
        if isinstance(node, ast.Raise) and isinstance(node.exc, ast.Call):
            yield node


def test_no_bare_exception_is_raised():
    """R10. `raise Exception(...)` tells a caller nothing and cannot be
    caught selectively — every raise site names a real exception type."""
    offenders = []
    for path in _iter_py_files():
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in _iter_raises(tree):
            func = node.exc.func  # type: ignore[union-attr]
            if isinstance(func, ast.Name) and func.id == "Exception":
                offenders.append(f"{path.relative_to(SRC)}:{node.lineno}")
    assert not offenders, f"raise Exception(...) found (R10): {offenders}"


def test_no_error_message_is_shorter_than_forty_characters():
    """R10. A message that fits in a tweet cannot name the setting, the bad
    value, and the remedy. Only a bare constant-string first argument is
    checked — an f-string or a variable is assumed to already carry that
    context, so `raise ValueError(f"...")` and `raise ValueError(msg)` are
    both out of scope for this check."""
    offenders = []
    for path in _iter_py_files():
        rel = str(path.relative_to(SRC))
        exempt_lines = SHORT_MESSAGE_EXCEPTIONS.get(rel, set())
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in _iter_raises(tree):
            call = node.exc
            if not call.args:  # type: ignore[union-attr]
                continue
            first = call.args[0]  # type: ignore[union-attr]
            if not (isinstance(first, ast.Constant) and isinstance(first.value, str)):
                continue
            if len(first.value) >= 40 or node.lineno in exempt_lines:
                continue
            offenders.append(f"{rel}:{node.lineno} {first.value!r}")
    assert not offenders, (
        f"Error message(s) under 40 characters, naming neither the setting "
        f"nor the remedy (R10): {offenders}"
    )


def test_config_mixins_share_one_naming_convention():
    """R11. Sibling classes in one package use one convention — every
    top-level class in `config/mixins/` ends in `Mixin` (AGENTS.md: `Mixin`
    means reusable)."""
    mixins_dir = SRC / "config" / "mixins"
    offenders = []
    for path in mixins_dir.glob("*.py"):
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in tree.body:
            if isinstance(node, ast.ClassDef) and not node.name.endswith("Mixin"):
                offenders.append(f"{path.relative_to(SRC)}:{node.lineno} {node.name}")
    assert not offenders, f"{offenders} should end in 'Mixin' (R11, ADR-0035)."
