import os


def is_wsl() -> bool:
    """Best-effort detection of WSL (``WSL_DISTRO_NAME`` or ``WSLENV``)."""
    return bool(os.environ.get("WSL_DISTRO_NAME") or os.environ.get("WSLENV"))


def is_termux() -> bool:
    """Best-effort detection of a Termux (Android) terminal.

    Checks ``TERMUX_VERSION``, a ``com.termux`` ``PREFIX``, then
    ``ANDROID_ROOT=/system`` (proot distros lose the first two).
    """
    if os.getenv("TERMUX_VERSION"):
        return True
    if "com.termux" in os.getenv("PREFIX", ""):
        return True
    if os.getenv("ANDROID_ROOT") == "/system":
        return True
    return False
