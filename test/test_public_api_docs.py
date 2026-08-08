"""Docstring coverage contract for the `zrb.*` public API surface.

Two rules, both aimed at the same failure: a user reading `help(X)` and being
told something incomplete or wrong.

1. Every public method and property on an exported class has a docstring.
2. Every exported class that *adds* constructor parameters documents them in
   its own ``__init__`` docstring.

Rule 2 exists because `inspect.getdoc` walks the MRO. Without it, `CmdTask`
(44 parameters) silently inherits `BaseTask`'s docstring describing 21, and
`help(CmdTask)` presents that as the complete argument list. A class that
redefines ``__init__`` without adding parameters is exempt — inheriting the
base description is correct there.
"""

import dataclasses
import inspect

import pytest

import zrb

EXPORTED_CLASSES = sorted(
    name for name in zrb.__all__ if inspect.isclass(getattr(zrb, name, None))
)

# Split up front rather than skipping inside the tests: a case parametrized over
# every export only to skip on the ones it does not apply to reports 49 skips
# that mean "not applicable", drowning the handful that mean something.
EXPORTED_DATACLASSES = sorted(
    name for name in EXPORTED_CLASSES if dataclasses.is_dataclass(getattr(zrb, name))
)
EXPORTED_NON_DATACLASSES = sorted(set(EXPORTED_CLASSES) - set(EXPORTED_DATACLASSES))


def _defines_init(cls: type) -> bool:
    return "__init__" in cls.__dict__


def _params(cls: type) -> list[str]:
    try:
        signature = inspect.signature(cls.__init__)
    except (TypeError, ValueError):  # pragma: no cover - unlikely for our classes
        return []
    return [name for name in signature.parameters if name != "self"]


def _inherited_params(cls: type) -> list[str]:
    """Parameters of the nearest ancestor that defines its own __init__.

    `object` does not count: its `(*args, **kwargs)` is not a signature anyone
    inherits meaning from, and treating it as one makes every base-less class
    with a no-arg constructor look like it narrowed something.
    """
    for ancestor in cls.__mro__[1:]:
        if ancestor is object:
            break
        if _defines_init(ancestor):
            return _params(ancestor)
    return []


def _own_params(cls: type) -> list[str]:
    """Parameters this class adds beyond the nearest ancestor defining __init__."""
    inherited = set(_inherited_params(cls))
    return [name for name in _params(cls) if name not in inherited]


def _signature_differs_from_ancestor(cls: type) -> bool:
    """Whether this class's constructor takes a different parameter set than its base.

    Adding parameters is the obvious case, but *removing* them matters just as
    much: `Cli()` takes none while `Group.__init__` takes three, so the
    docstring it inherits documented arguments it rejects.
    """
    return set(_params(cls)) != set(_inherited_params(cls))


@pytest.mark.parametrize("class_name", EXPORTED_CLASSES)
def test_public_members_have_docstrings(class_name):
    # Arrange
    cls = getattr(zrb, class_name)
    # Act
    undocumented = []
    for name, member in inspect.getmembers(
        cls, lambda x: inspect.isfunction(x) or isinstance(x, property)
    ):
        if name.startswith("_"):
            continue
        target = member.fget if isinstance(member, property) else member
        module = getattr(target, "__module__", None)
        if not module or not module.startswith("zrb"):
            continue
        if not inspect.getdoc(member):
            undocumented.append(name)
    # Assert
    assert (
        not undocumented
    ), f"{class_name} has public members without a docstring: {undocumented}"


@pytest.mark.parametrize("class_name", EXPORTED_DATACLASSES)
def test_dataclasses_document_themselves_at_class_level(class_name):
    """A dataclass's generated `__init__` carries no docstring by design.

    Its fields appear in the class signature with their types and defaults, so
    the documentation belongs on the class, not on a synthesized method.
    """
    # Arrange
    cls = getattr(zrb, class_name)
    # Act
    docstring = (cls.__doc__ or "").strip()
    # Assert
    assert docstring, f"dataclass {class_name} has no class docstring"


@pytest.mark.parametrize("class_name", EXPORTED_NON_DATACLASSES)
def test_constructors_document_the_parameters_they_add(class_name):
    # Arrange
    cls = getattr(zrb, class_name)
    own = _own_params(cls)
    if not _defines_init(cls) or not _signature_differs_from_ancestor(cls):
        pytest.skip(f"{class_name} takes the same parameters as its base")
    # Act
    docstring = cls.__init__.__doc__ or ""
    missing = [name for name in own if f"{name}:" not in docstring]
    # Assert
    assert docstring.strip(), (
        f"{class_name}.__init__ takes a different parameter set than its base but "
        f"has no docstring of its own, so help({class_name}) shows an ancestor's "
        f"description of a different signature. Own parameters: {own}"
    )
    assert not missing, (
        f"{class_name}.__init__ does not document {len(missing)} parameter(s) it "
        f"adds: {missing}"
    )
