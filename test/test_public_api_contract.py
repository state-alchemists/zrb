"""Golden-file contract for the `zrb.*` public API surface.

This is the regression net for refactors that reshape public signatures
(constructor grouping, parameter collapse, method extraction). It pins three
things per exported name:

  * membership of ``zrb.__all__``
  * every public method/property on each exported class
  * every ``__init__`` parameter that zrb itself defines: name, order, kind,
    and *whether* it has a default

``__init__`` inherited from a non-zrb base (``enum.Enum``, a pydantic model, a
``typing.Protocol``) is not pinned: its signature is upstream-controlled and can
shift across Python versions (CPython renamed Enum's ``**kwargs`` to ``**kwds``
in 3.13), which would make the snapshot unstable for no zrb change.

Defaults are recorded as a boolean, never by value. Several defaults are live
singletons (``llm_config``, ``hook_manager``) whose ``repr`` carries a memory
address, so pinning values would make the snapshot unstable across runs. The
boolean still catches what matters: a parameter dropped, renamed, reordered,
or turned from optional into required.

To accept an intentional change, review the diff and regenerate:

    ZRB_UPDATE_API_SNAPSHOT=1 pytest test/test_public_api_contract.py
"""

import inspect
import json
import os
import pathlib

import pytest

import zrb

SNAPSHOT_PATH = pathlib.Path(__file__).parent / "public_api_snapshot.json"


def _signature_of(func) -> list[str]:
    """Describe a callable's parameters as stable ``name:kind:has_default`` rows."""
    try:
        signature = inspect.signature(func)
    except (TypeError, ValueError):  # pragma: no cover - builtins without signature
        return []
    rows = []
    for name, param in signature.parameters.items():
        if name == "self":
            continue
        has_default = param.default is not inspect.Parameter.empty
        rows.append(f"{name}:{param.kind.name}:{int(has_default)}")
    return rows


def _class_init_of(cls: type) -> list[str]:
    """Describe ``__init__`` parameters only when zrb defines the constructor.

    ``cls.__init__`` may be inherited from a non-zrb base (``enum.Enum``, a
    pydantic ``BaseModel``, a ``typing.Protocol``), whose signature is controlled
    upstream and can vary across Python versions (CPython renamed Enum's
    ``**kwargs`` to ``**kwds`` in 3.13). That signature is not zrb's public
    contract, so it is not pinned — mirroring the zrb-ownership filter that
    ``_public_members`` already applies.
    """
    module = getattr(cls.__init__, "__module__", None)
    if not module or not module.startswith("zrb"):
        return []
    return _signature_of(cls.__init__)


def _public_members(cls: type) -> list[str]:
    """List public methods and properties that `cls` defines or inherits from zrb."""
    names = []
    for name, member in inspect.getmembers(
        cls, lambda x: inspect.isfunction(x) or isinstance(x, property)
    ):
        if name.startswith("_"):
            continue
        target = member.fget if isinstance(member, property) else member
        module = getattr(target, "__module__", None)
        if not module or not module.startswith("zrb"):
            continue
        names.append(name)
    return sorted(names)


def build_surface() -> dict:
    """Snapshot the whole exported API surface as plain, diffable JSON."""
    surface = {"__all__": sorted(zrb.__all__), "classes": {}, "functions": {}}
    for name in sorted(zrb.__all__):
        obj = getattr(zrb, name, None)
        if inspect.isclass(obj):
            surface["classes"][name] = {
                "init": _class_init_of(obj),
                "members": _public_members(obj),
            }
        elif inspect.isfunction(obj):
            surface["functions"][name] = _signature_of(obj)
    return surface


@pytest.fixture(scope="module")
def snapshot() -> dict:
    """Load the golden file, regenerating it first when explicitly requested."""
    current = build_surface()
    if os.environ.get("ZRB_UPDATE_API_SNAPSHOT"):
        SNAPSHOT_PATH.write_text(json.dumps(current, indent=2, sort_keys=True) + "\n")
    assert SNAPSHOT_PATH.exists(), (
        f"{SNAPSHOT_PATH} is missing. Generate it with "
        "ZRB_UPDATE_API_SNAPSHOT=1 pytest test/test_public_api_contract.py"
    )
    return json.loads(SNAPSHOT_PATH.read_text())


def test_exported_names_are_unchanged(snapshot):
    # Arrange / Act
    current = build_surface()["__all__"]
    # Assert
    assert current == snapshot["__all__"], (
        "zrb.__all__ changed. Removing an export breaks user code; adding one is "
        "fine but must be recorded via ZRB_UPDATE_API_SNAPSHOT=1."
    )


def test_exported_class_constructors_are_unchanged(snapshot):
    # Arrange
    current = build_surface()["classes"]
    # Act
    drifted = {
        name: (snapshot["classes"][name]["init"], spec["init"])
        for name, spec in current.items()
        if name in snapshot["classes"]
        and spec["init"] != snapshot["classes"][name]["init"]
    }
    # Assert
    assert not drifted, _render_drift(drifted, "constructor parameters")


def test_exported_class_members_are_unchanged(snapshot):
    # Arrange
    current = build_surface()["classes"]
    # Act
    drifted = {
        name: (snapshot["classes"][name]["members"], spec["members"])
        for name, spec in current.items()
        if name in snapshot["classes"]
        and spec["members"] != snapshot["classes"][name]["members"]
    }
    # Assert
    assert not drifted, _render_drift(drifted, "members")


def test_exported_functions_are_unchanged(snapshot):
    # Arrange
    current = build_surface()["functions"]
    # Act
    drifted = {
        name: (snapshot["functions"][name], spec)
        for name, spec in current.items()
        if name in snapshot["functions"] and spec != snapshot["functions"][name]
    }
    # Assert
    assert not drifted, _render_drift(drifted, "function parameters")


def _render_drift(drifted: dict, subject: str) -> str:
    """Render a removed/added diff per drifted name, so failures name the culprit."""
    lines = [f"Public {subject} drifted from the recorded snapshot:"]
    for name, (expected, actual) in sorted(drifted.items()):
        removed = [item for item in expected if item not in actual]
        added = [item for item in actual if item not in expected]
        lines.append(f"  {name}:")
        if removed:
            lines.append(f"    removed: {removed}")
        if added:
            lines.append(f"    added:   {added}")
        if not removed and not added:
            lines.append(f"    reordered: {expected} -> {actual}")
    lines.append(
        "Removals and reorderings break user code. If the change is intended, "
        "regenerate with ZRB_UPDATE_API_SNAPSHOT=1."
    )
    return "\n".join(lines)
