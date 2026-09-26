"""Retention for FileSessionStateLogger: logs past it are pruned, with their
timeline entries, at most once a day per directory."""

import os
import time
from datetime import datetime

from zrb.session_state_log.session_state_log import SessionStateLog
from zrb.session_state_logger.file_session_state_logger import FileSessionStateLogger


def _log(name: str) -> SessionStateLog:
    return SessionStateLog(
        name=name,
        start_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f"),
        main_task_name="task",
        path=["group"],
        input={},
        final_result="",
        finished=True,
        log=[],
        task_status={},
    )


def _age(path, seconds: float) -> None:
    stamp = time.time() - seconds
    os.utime(path, (stamp, stamp))


def _timeline_names(root) -> set[str]:
    return {name for _, _, names in os.walk(root / "_timeline") for name in names}


def _listed(logger) -> list[str]:
    result = logger.list(["group"], datetime(2000, 1, 1), datetime(2100, 1, 1))
    return [log.name for log in result.data]


def test_logs_past_their_retention_are_pruned_with_their_timeline(tmp_path):
    FileSessionStateLogger(str(tmp_path)).write(_log("old"))
    _age(tmp_path / "old.json", 3600)

    logger = FileSessionStateLogger(str(tmp_path), retention_seconds=60)
    logger.write(_log("new"))

    assert not (tmp_path / "old.json").exists()
    assert (tmp_path / "new.json").exists()
    assert _timeline_names(tmp_path) == {"new"}
    assert _listed(logger) == ["new"]


def test_the_session_being_written_is_never_pruned(tmp_path):
    FileSessionStateLogger(str(tmp_path)).write(_log("resumed"))
    _age(tmp_path / "resumed.json", 3600)

    FileSessionStateLogger(str(tmp_path), retention_seconds=60).write(_log("resumed"))

    assert (tmp_path / "resumed.json").exists()


def test_pruning_runs_at_most_once_a_day(tmp_path):
    FileSessionStateLogger(str(tmp_path), retention_seconds=60).write(_log("first"))
    FileSessionStateLogger(str(tmp_path)).write(_log("old"))
    _age(tmp_path / "old.json", 3600)

    FileSessionStateLogger(str(tmp_path), retention_seconds=60).write(_log("second"))

    assert (tmp_path / "old.json").exists()


def test_zero_retention_keeps_every_log(tmp_path):
    FileSessionStateLogger(str(tmp_path)).write(_log("old"))
    _age(tmp_path / "old.json", 10**8)

    FileSessionStateLogger(str(tmp_path), retention_seconds=lambda: 0).write(
        _log("new")
    )

    assert (tmp_path / "old.json").exists()


def test_listing_skips_a_timeline_entry_whose_log_is_gone(tmp_path):
    logger = FileSessionStateLogger(str(tmp_path))
    logger.write(_log("kept"))
    logger.write(_log("gone"))
    os.remove(tmp_path / "gone.json")

    assert _listed(logger) == ["kept"]


def test_the_prune_interval_is_configurable(tmp_path):
    FileSessionStateLogger(str(tmp_path), retention_seconds=60).write(_log("first"))
    FileSessionStateLogger(str(tmp_path)).write(_log("old"))
    _age(tmp_path / "old.json", 3600)

    FileSessionStateLogger(
        str(tmp_path), retention_seconds=60, prune_interval_seconds=lambda: 0
    ).write(_log("second"))

    assert not (tmp_path / "old.json").exists()


def test_the_factory_reads_both_durations_from_cfg(tmp_path, monkeypatch):
    from zrb.session_state_logger.session_state_logger_factory import (
        session_state_logger,
    )

    monkeypatch.setenv("ZRB_SESSION_LOG_DIR", str(tmp_path))
    monkeypatch.setenv("ZRB_SESSION_LOG_RETENTION", "1m")
    monkeypatch.setenv("ZRB_SESSION_LOG_PRUNE_INTERVAL", "0")
    FileSessionStateLogger(str(tmp_path)).write(_log("old"))
    _age(tmp_path / "old.json", 3600)

    session_state_logger.write(_log("new"))

    assert not (tmp_path / "old.json").exists()
