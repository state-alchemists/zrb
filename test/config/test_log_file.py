import io
import logging
import sys

import pytest

from zrb.__main__ import _handle_uncaught, serve_cli
from zrb.config.config import CFG
from zrb.config.log_file import has_file_log_handler, install_file_log_handler

STUTTER = "Speech stuttered: 3 block(s) of audio were not standing by in time"


def _fresh_logger(name: str) -> logging.Logger:
    """A logger of its own, so a handler added here reaches no other test."""
    logger = logging.getLogger(name)
    logger.handlers.clear()
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    return logger


def test_no_file_is_written_unless_one_is_configured(tmp_path, monkeypatch):
    """Empty is the default and means no file at all, not a file somewhere."""
    monkeypatch.delenv("ZRB_LOGGING_FILE", raising=False)
    logger = _fresh_logger("zrb.test.log_file.unconfigured")
    install_file_log_handler(logger)
    assert has_file_log_handler(logger) is False
    assert logger.handlers == []
    assert list(tmp_path.iterdir()) == []


def test_the_file_keeps_a_warning_the_terminal_would_show(monkeypatch, tmp_path):
    """The whole point: a line the UI paints over still lands on disk."""
    log_path = tmp_path / "zrb.log"
    monkeypatch.setenv("ZRB_LOGGING_FILE", str(log_path))
    monkeypatch.delenv("ZRB_LOGGING_FILE_LEVEL", raising=False)
    monkeypatch.setenv("ZRB_LOGGING_LEVEL", "WARNING")
    logger = _fresh_logger("zrb.test.log_file.warning")

    install_file_log_handler(logger)
    assert has_file_log_handler(logger) is True
    logger.warning(STUTTER)

    assert STUTTER in log_path.read_text(encoding="utf-8")


def test_the_file_follows_the_terminals_level_by_default(monkeypatch, tmp_path):
    """An unset file level is the terminal's level, so nothing new is kept."""
    log_path = tmp_path / "zrb.log"
    monkeypatch.setenv("ZRB_LOGGING_FILE", str(log_path))
    monkeypatch.delenv("ZRB_LOGGING_FILE_LEVEL", raising=False)
    monkeypatch.setenv("ZRB_LOGGING_LEVEL", "WARNING")
    logger = _fresh_logger("zrb.test.log_file.same_level")

    install_file_log_handler(logger)
    logger.info("an info the terminal does not show")
    logger.warning(STUTTER)

    written = log_path.read_text(encoding="utf-8")
    assert STUTTER in written
    assert "an info the terminal does not show" not in written


def test_the_file_level_can_be_more_verbose_than_the_terminal(monkeypatch, tmp_path):
    """DEBUG in the file while the screen stays at WARNING is the reason the
    file has a level of its own."""
    log_path = tmp_path / "zrb.log"
    monkeypatch.setenv("ZRB_LOGGING_FILE", str(log_path))
    monkeypatch.setenv("ZRB_LOGGING_FILE_LEVEL", "DEBUG")
    monkeypatch.setenv("ZRB_LOGGING_LEVEL", "WARNING")
    logger = _fresh_logger("zrb.test.log_file.own_level")

    install_file_log_handler(logger)
    logger.debug("the callback asked for 4096 frames")

    assert "asked for 4096 frames" in log_path.read_text(encoding="utf-8")
    assert CFG.LOGGING_LEVEL == logging.WARNING


def test_asking_twice_adds_one_handler(monkeypatch, tmp_path):
    """`serve_cli` may configure logging more than once in one process; a line
    written twice would read as two stalls."""
    monkeypatch.setenv("ZRB_LOGGING_FILE", str(tmp_path / "zrb.log"))
    logger = _fresh_logger("zrb.test.log_file.twice")

    install_file_log_handler(logger)
    install_file_log_handler(logger)
    assert has_file_log_handler(logger) is True

    assert len(logger.handlers) == 1


def test_a_grown_file_rotates_and_the_backup_is_kept(monkeypatch, tmp_path):
    log_path = tmp_path / "zrb.log"
    monkeypatch.setenv("ZRB_LOGGING_FILE", str(log_path))
    monkeypatch.setenv("ZRB_LOGGING_FILE_MAX_BYTES", "300")
    monkeypatch.setenv("ZRB_LOGGING_FILE_BACKUP_COUNT", "1")
    logger = _fresh_logger("zrb.test.log_file.rotating")

    install_file_log_handler(logger)
    for index in range(40):
        logger.warning(f"{STUTTER} (#{index})")

    assert log_path.exists()
    assert (tmp_path / "zrb.log.1").exists()


def test_a_max_size_of_zero_never_rotates(monkeypatch, tmp_path):
    """Documented: 0 means the file keeps growing, nothing is moved aside."""
    log_path = tmp_path / "zrb.log"
    monkeypatch.setenv("ZRB_LOGGING_FILE", str(log_path))
    monkeypatch.setenv("ZRB_LOGGING_FILE_MAX_BYTES", "0")
    monkeypatch.setenv("ZRB_LOGGING_FILE_BACKUP_COUNT", "0")
    logger = _fresh_logger("zrb.test.log_file.no_rotation")

    install_file_log_handler(logger)
    for index in range(40):
        logger.warning(f"{STUTTER} (#{index})")

    assert not (tmp_path / "zrb.log.1").exists()


def test_a_missing_directory_is_created(monkeypatch, tmp_path):
    log_path = tmp_path / "deep" / "logs" / "zrb.log"
    monkeypatch.setenv("ZRB_LOGGING_FILE", str(log_path))
    logger = _fresh_logger("zrb.test.log_file.mkdir")

    install_file_log_handler(logger)
    assert has_file_log_handler(logger) is True
    assert log_path.exists()


def test_serve_cli_wires_the_configured_file(tmp_path, monkeypatch):
    """The wiring, not just the helper: a chat started by the CLI keeps its
    warnings without anyone opting in twice."""
    log_path = tmp_path / "logs" / "zrb.log"
    monkeypatch.setenv("ZRB_LOGGING_FILE", str(log_path))
    monkeypatch.setenv("ZRB_INIT_STRICT", "off")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["zrb"])
    before = CFG.LOGGER.handlers[:]
    try:
        serve_cli()
        assert log_path.exists()
        CFG.LOGGER.warning(STUTTER)
        assert STUTTER in log_path.read_text(encoding="utf-8")
    finally:
        for handler in CFG.LOGGER.handlers[:]:
            if handler in before:
                continue
            CFG.LOGGER.removeHandler(handler)
            handler.close()


def test_an_init_source_can_override_logging(tmp_path, monkeypatch):
    """`zrb_init.py` loads after the first logging pass; its choice must win.

    The first pass exists to keep startup warnings. Without a second pass, a
    level or file set by the user's init source would be silently ignored.
    """
    log_path = tmp_path / "from-init.log"
    (tmp_path / "zrb_init.py").write_text(
        "from zrb.config.config import CFG\n"
        f"CFG.LOGGING_FILE = {str(log_path)!r}\n"
        "CFG.LOGGING_LEVEL = 'DEBUG'\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("ZRB_INIT_STRICT", "off")
    monkeypatch.setenv("ZRB_LOGGING_LEVEL", "WARNING")
    monkeypatch.setenv("ZRB_LOGGING_FILE", "")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["zrb"])
    before = CFG.LOGGER.handlers[:]
    before_level = CFG.LOGGER.level
    try:
        serve_cli()
        assert CFG.LOGGING_LEVEL == logging.DEBUG
        assert CFG.LOGGER.level == logging.DEBUG
        assert has_file_log_handler(CFG.LOGGER) is True
        assert log_path.exists()
    finally:
        for handler in CFG.LOGGER.handlers[:]:
            CFG.LOGGER.removeHandler(handler)
            if handler not in before and isinstance(handler, logging.FileHandler):
                handler.close()
        for handler in before:
            CFG.LOGGER.addHandler(handler)
        CFG.LOGGER.setLevel(before_level)


def test_a_more_verbose_file_keeps_the_screen_quiet(monkeypatch, tmp_path):
    """`LOGGING_FILE_LEVEL` under the terminal's level is the whole reason the
    file has one, and a logger drops a record before its handlers see it — so
    the logger level has to come down while the screen is pinned where it was.
    """
    log_path = tmp_path / "zrb.log"
    monkeypatch.setenv("ZRB_LOGGING_FILE", str(log_path))
    monkeypatch.setenv("ZRB_LOGGING_FILE_LEVEL", "DEBUG")
    monkeypatch.setenv("ZRB_LOGGING_LEVEL", "WARNING")
    logger = _fresh_logger("zrb.test.log_file.quiet_screen")
    logger.setLevel(logging.WARNING)
    screen = logging.StreamHandler(io.StringIO())
    logger.addHandler(screen)

    install_file_log_handler(logger)
    logger.debug("the callback asked for 4096 frames")
    logger.warning(STUTTER)

    assert "asked for 4096 frames" in log_path.read_text(encoding="utf-8")
    shown = screen.stream.getvalue()
    assert STUTTER in shown
    assert "asked for 4096 frames" not in shown


def test_the_file_level_does_not_turn_a_failure_into_a_traceback(
    monkeypatch, tmp_path, capsys
):
    """A file asking for DEBUG lowers `CFG.LOGGER`; a failed task must still
    print one clean line, because the screen was never asked for detail."""
    monkeypatch.setenv("ZRB_LOGGING_FILE", str(tmp_path / "zrb.log"))
    monkeypatch.setenv("ZRB_LOGGING_FILE_LEVEL", "DEBUG")
    monkeypatch.setenv("ZRB_LOGGING_LEVEL", "WARNING")
    before = CFG.LOGGER.handlers[:]
    before_level = CFG.LOGGER.level
    try:
        install_file_log_handler()
        assert CFG.LOGGER.isEnabledFor(logging.DEBUG), "the trap this guards"
        with pytest.raises(SystemExit):
            _handle_uncaught(RuntimeError("boom"))
        captured = capsys.readouterr()
        assert "RuntimeError: boom" in captured.err
        assert "Traceback" not in captured.err
    finally:
        for handler in CFG.LOGGER.handlers[:]:
            if handler in before:
                continue
            CFG.LOGGER.removeHandler(handler)
            handler.close()
        CFG.LOGGER.setLevel(before_level)


def test_running_the_cli_twice_does_not_leak_a_file_handler(tmp_path, monkeypatch):
    """`serve_cli` may run more than once in one process. Each pass drops the
    handlers before adding its own, so a file handler left open would be one
    descriptor per pass."""
    monkeypatch.setenv("ZRB_LOGGING_FILE", str(tmp_path / "zrb.log"))
    monkeypatch.setenv("ZRB_INIT_STRICT", "off")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["zrb"])
    before = CFG.LOGGER.handlers[:]
    before_level = CFG.LOGGER.level
    try:
        serve_cli()
        first = [
            handler
            for handler in CFG.LOGGER.handlers
            if getattr(handler, "_zrb_log_file_handler", False)
        ]
        assert len(first) == 1

        serve_cli()
        assert len(CFG.LOGGER.handlers) == 2, "one screen handler, one file handler"
        assert (
            getattr(first[0], "stream", "unopened") is None
        ), "the file the first pass opened is closed"
    finally:
        for handler in CFG.LOGGER.handlers[:]:
            CFG.LOGGER.removeHandler(handler)
            if handler not in before and isinstance(handler, logging.FileHandler):
                handler.close()
        for handler in before:
            CFG.LOGGER.addHandler(handler)
        CFG.LOGGER.setLevel(before_level)
