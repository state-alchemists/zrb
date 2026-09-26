"""Retention for FileHistoryManager: auto-named conversations past
`LLM_HISTORY_RETENTION` are pruned, with their backups, on the first save of
a session; conversations someone named are kept forever."""

import os
import time
from unittest.mock import patch

import pytest
from pydantic_ai.messages import ModelRequest, UserPromptPart

from zrb.llm.history_manager.file_history_manager import FileHistoryManager


@pytest.fixture
def history_dir(tmp_path):
    return tmp_path


def _write(history_dir, name: str, age_seconds: float = 0) -> str:
    path = os.path.join(history_dir, f"{name}.json")
    with open(path, "w") as f:
        f.write("[]")
    stamp = time.time() - age_seconds
    os.utime(path, (stamp, stamp))
    return path


def _save(manager: FileHistoryManager, name: str) -> None:
    manager.update(name, [ModelRequest(parts=[UserPromptPart(content="hi")])])
    manager.save(name, write_backup=False)


@pytest.fixture
def retention():
    with patch(
        "zrb.llm.history_manager.file_history_manager.CFG"
    ) as cfg:
        cfg.LLM_HISTORY_RETENTION = "1d"
        cfg.LLM_HISTORY_BACKUP_RETAIN = 0
        yield cfg


def test_an_expired_auto_named_conversation_is_pruned_with_its_backups(
    history_dir, retention
):
    old = _write(history_dir, "bold-arch-1234", age_seconds=3 * 86400)
    old_backup = _write(
        history_dir, "bold-arch-1234-2024-01-01-10-00-00", age_seconds=3 * 86400
    )
    fresh = _write(history_dir, "calm-atom-5678", age_seconds=60)

    _save(FileHistoryManager(str(history_dir)), "warm-base-0001")

    assert not os.path.exists(old)
    assert not os.path.exists(old_backup)
    assert os.path.exists(fresh)


def test_a_named_conversation_is_kept_however_old(history_dir, retention):
    named = _write(history_dir, "my-project", age_seconds=365 * 86400)

    _save(FileHistoryManager(str(history_dir)), "warm-base-0001")

    assert os.path.exists(named)


def test_the_conversation_being_saved_is_never_pruned(history_dir, retention):
    _write(history_dir, "bold-arch-1234", age_seconds=3 * 86400)

    _save(FileHistoryManager(str(history_dir)), "bold-arch-1234")

    assert os.path.exists(os.path.join(history_dir, "bold-arch-1234.json"))


def test_pruning_runs_once_per_manager(history_dir, retention):
    manager = FileHistoryManager(str(history_dir))
    _save(manager, "warm-base-0001")
    old = _write(history_dir, "bold-arch-1234", age_seconds=3 * 86400)

    _save(manager, "warm-base-0001")

    assert os.path.exists(old)


def test_zero_retention_keeps_every_conversation(history_dir, retention):
    retention.LLM_HISTORY_RETENTION = "0"
    old = _write(history_dir, "bold-arch-1234", age_seconds=10**8)

    _save(FileHistoryManager(str(history_dir)), "warm-base-0001")

    assert os.path.exists(old)
