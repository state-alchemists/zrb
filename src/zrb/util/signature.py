"""Read what a user-supplied callable accepts from its signature."""

import inspect
from collections.abc import Callable
from inspect import Parameter


def can_take_positional(
    func: Callable[..., object], count: int, if_unknown: bool
) -> bool:
    """Whether *func* accepts *count* positional arguments.

    Read from the signature rather than discovered from a `TypeError`, which a
    real failure inside *func* looks exactly like. *if_unknown* answers for a
    callable that cannot be introspected (a builtin or C function).
    """
    try:
        parameters = inspect.signature(func).parameters.values()
    except (TypeError, ValueError):
        return if_unknown
    if any(p.kind is Parameter.VAR_POSITIONAL for p in parameters):
        return True
    positional_kinds = (Parameter.POSITIONAL_ONLY, Parameter.POSITIONAL_OR_KEYWORD)
    return sum(p.kind in positional_kinds for p in parameters) >= count
