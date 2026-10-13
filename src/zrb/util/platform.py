import os


def is_wsl() -> bool:
    """Best-effort detection of WSL (``WSL_DISTRO_NAME`` or ``WSLENV``)."""
    return bool(os.environ.get("WSL_DISTRO_NAME") or os.environ.get("WSLENV"))
