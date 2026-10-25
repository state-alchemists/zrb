"""An optional log file, for the lines a repainting terminal loses.

The chat UI draws its own screen, so a warning written to stderr is painted
over by the next frame and never read again — which is how a stutter only
ever reproducible "while the machine is busy" stayed undiagnosable. A file
keeps the line, rotated, so it can be read after the fact.
"""

from __future__ import annotations

import logging
import logging.handlers
import os

from zrb.config.config import CFG
from zrb.config.helper import get_log_level

# Marks the handler this module added: asking twice must not write twice.
_FILE_HANDLER_MARK = "_zrb_log_file_handler"
_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def install_file_log_handler(logger: logging.Logger | None = None) -> None:
    """Write logs to `CFG.LOGGING_FILE` as well, when one is configured.

    Asking twice adds nothing, recognized by `_FILE_HANDLER_MARK`, so a CLI
    that configures logging twice does not write every line twice. The file's
    directory is created when missing.

    A file that cannot be opened is reported and left alone rather than
    raised: a chat that cannot log is still a chat that runs.

    `has_file_log_handler` answers whether a file is being written.
    """
    target = CFG.LOGGER if logger is None else logger
    path = (CFG.LOGGING_FILE or "").strip()
    if not path:
        return
    if has_file_log_handler(target):
        return
    try:
        handler = _build_handler(os.path.expanduser(path))
    except OSError as exc:
        target.warning(f"LOGGING_FILE {path!r} cannot be opened: {exc}")
        return
    target.addHandler(handler)


def has_file_log_handler(logger: logging.Logger | None = None) -> bool:
    """Whether *logger* — `CFG.LOGGER` left out — is writing a log file."""
    target = CFG.LOGGER if logger is None else logger
    return any(
        getattr(handler, _FILE_HANDLER_MARK, False) for handler in target.handlers
    )


def _build_handler(path: str) -> logging.Handler:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    handler = logging.handlers.RotatingFileHandler(
        path,
        maxBytes=max(0, CFG.LOGGING_FILE_MAX_BYTES),
        backupCount=max(0, CFG.LOGGING_FILE_BACKUP_COUNT),
        encoding="utf-8",
    )
    handler.setLevel(_file_level())
    handler.setFormatter(logging.Formatter(_FORMAT, _DATE_FORMAT))
    setattr(handler, _FILE_HANDLER_MARK, True)
    return handler


def _file_level() -> int:
    """`LOGGING_FILE_LEVEL` when set, otherwise the terminal's own level."""
    configured = (CFG.LOGGING_FILE_LEVEL or "").strip()
    return get_log_level(configured) if configured else CFG.LOGGING_LEVEL
