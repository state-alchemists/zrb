"""Exception display helpers — turning an exception into a non-empty string."""


def exception_summary(exc: BaseException) -> str:
    """Return a description of ``exc`` that is never empty.

    ``str(exc)`` is empty for a bare ``raise SomeError()``, so the type name
    is prefixed — unless the message already quotes it, as many provider
    errors do.
    """
    message = str(exc)
    if not message:
        return type(exc).__name__
    if type(exc).__name__ in message:
        return message
    return f"{type(exc).__name__}: {message}"
