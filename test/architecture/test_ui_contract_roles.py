"""Keep `AnyUI`'s five roles a partition of its members, not a second copy.

`any_ui.py` composes `AnyUIDisplay`, `AnyUIInput`, `AnyUIPicker`, `AnyUITools`
and `AnyUISession`. That only stays honest if each member is declared in exactly
one place: a member declared twice can drift, and one declared nowhere is a
member nobody promised. Read from the syntax, so an import cycle cannot hide it.
"""

import ast
import pathlib

REPO_ROOT = pathlib.Path(__file__).parents[2]
LLM = REPO_ROOT / "src" / "zrb" / "llm"

# The contract files, and the class each one declares. `any_ui.py` holds what
# belongs to the whole rather than to a role.
ROLE_FILES = {
    "any_ui_display.py": "AnyUIDisplay",
    "any_ui_input.py": "AnyUIInput",
    "any_ui_picker.py": "AnyUIPicker",
    "any_ui_session.py": "AnyUISession",
    "any_ui_tools.py": "AnyUITools",
}
CORE_FILE = "any_ui.py"
CORE_CLASS = "AnyUI"

# A role reached through an accessor instead of by inheritance: a UI hands out
# its choice widget rather than answering to every one of its methods. Every
# role not named here must reach `AnyUI` as a base, member for member.
ROLE_ACCESSOR = {"AnyUIPicker": "picker"}

# `AnyUI` itself holds only the whole-object members: run the loop, say whether
# the user is local, link to a `MultiUI` parent, and hand out the roles that are
# not bases. A member that is really a role belongs in that role's file.
CORE_MEMBERS = {
    "run_async",
    "is_local",
    "multi_ui_parent",
    "display",
    "input",
    "picker",
    "tools",
    "session",
}
MAX_CORE_MEMBERS = 8

# `AnyUI`'s own declared members. The target is 25; this may only be lowered as
# roles move behind their parts, never raised to admit a member.
ANY_UI_MEMBERS = 4


def _members(path: pathlib.Path, class_name: str) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            return {
                member.name
                for member in node.body
                if isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef))
            }
    raise AssertionError(f"{path.name} no longer declares {class_name}")


def _declared() -> dict[str, set[str]]:
    declared = {
        class_name: _members(LLM / file_name, class_name)
        for file_name, class_name in ROLE_FILES.items()
    }
    declared[CORE_CLASS] = _members(LLM / CORE_FILE, CORE_CLASS)
    return declared


def test_no_member_is_declared_twice():
    declared = _declared()
    seen: dict[str, str] = {}
    overlaps: list[str] = []
    for class_name, members in declared.items():
        for member in members:
            if member in seen:
                overlaps.append(f"{member} in {seen[member]} and {class_name}")
            seen[member] = class_name
    assert not overlaps, (
        "A UI member is declared in more than one contract, so the two can "
        f"drift apart: {overlaps}"
    )


def test_every_role_member_reaches_the_whole_object():
    from zrb.llm.any_ui import AnyUI

    missing: list[str] = []
    for class_name, members in _declared().items():
        accessor = ROLE_ACCESSOR.get(class_name)
        if accessor is not None:
            if not hasattr(AnyUI, accessor):
                missing.append(f"{class_name} through `{accessor}`")
            continue
        missing += [
            f"{class_name}.{member}"
            for member in sorted(members)
            if not hasattr(AnyUI, member)
        ]
    assert not missing, (
        "A role declares a member `AnyUI` does not expose, so a caller typed "
        f"against the whole object cannot reach it: {missing}"
    )


def test_the_core_keeps_only_the_whole_object_members():
    core = _declared()[CORE_CLASS]
    extra = sorted(core - CORE_MEMBERS)
    assert not extra, (
        f"`AnyUI` declares {extra}, which belong to a role, not to the whole "
        "object. Move each into its role contract."
    )
    assert len(core) <= MAX_CORE_MEMBERS, (
        f"`AnyUI`'s own member count grew to {len(core)}; it holds the whole-"
        f"object members only, at most {MAX_CORE_MEMBERS}."
    )


def test_the_member_ratchet_is_tight():
    own = len(_declared()[CORE_CLASS])
    assert own <= ANY_UI_MEMBERS, (
        f"`AnyUI` declares {own} members, up from {ANY_UI_MEMBERS}. A role is "
        "meant to replace a member, not add one."
    )
    assert own == ANY_UI_MEMBERS, (
        f"{ANY_UI_MEMBERS - own} member(s) left `AnyUI` without lowering "
        f"ANY_UI_MEMBERS. Set it to {own}."
    )
