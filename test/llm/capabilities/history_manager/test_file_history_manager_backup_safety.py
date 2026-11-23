"""Backups stay inside the history tree, never impersonate a conversation, and
never publish each other's bytes.

Three defects shared one cause: a backup was just another `<name>-<timestamp>.json`
beside the live transcript. A client-supplied conversation name could therefore
put one outside `LLM_HISTORY_DIR`; a real conversation whose name ends in a
timestamp looked like a backup of another one and was deleted by rotation; and
two saves of the same conversation shared one predictable `.tmp` inode.
"""

import json
import os
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest
from pydantic_ai.messages import ModelRequest, UserPromptPart

import zrb.llm.capabilities.history_manager.file_history_manager as history_module
from zrb.config.config import CFG
from zrb.llm.capabilities.history_manager.file_history_manager import FileHistoryManager


def _save(manager: FileHistoryManager, name: str) -> None:
    manager.update(name, [ModelRequest(parts=[UserPromptPart(content="hi")])])
    manager.save(name)


def test_a_traversing_conversation_name_cannot_write_a_backup_outside_history(
    tmp_path,
):
    """`../escaped` is sanitized into one segment for the live file, and the
    backup path must be sanitized and contained the same way."""
    history_dir = tmp_path / "history"
    manager = FileHistoryManager(str(history_dir))

    _save(manager, "../escaped")

    assert (history_dir / "..escaped.json").exists()
    assert not list(tmp_path.glob("escaped*.json"))
    assert [path for path in tmp_path.iterdir() if path.suffix == ".json"] == []

    backups = [path for path in (history_dir / "backups").rglob("*.json")]
    assert backups, "expected the backup to land inside the history directory"
    assert all(path.is_relative_to(history_dir / "backups") for path in backups)


def test_rotation_never_deletes_timestamp_named_live_conversations(
    tmp_path, monkeypatch
):
    """A conversation named `standup-2026-11-20-09-00` is not a backup of
    `standup`. With one backup retained, the old rotation deleted the other two
    live conversations on the last save."""
    monkeypatch.setattr(CFG, "LLM_HISTORY_BACKUP_RETAIN", 1, raising=False)
    manager = FileHistoryManager(str(tmp_path))
    names = [
        "standup-2026-11-20-09-00",
        "standup-2026-11-20-10-00",
        "standup-2026-11-20-11-00",
    ]

    for index, name in enumerate(names):
        manager.update(
            name, [ModelRequest(parts=[UserPromptPart(content=f"hi {index}")])]
        )
        manager.save(name)
        for live_name in names[: index + 1]:
            assert (
                tmp_path / f"{live_name}.json"
            ).exists(), f"live conversation {live_name} deleted by the save of {name}"

    assert set(os.listdir(tmp_path / "backups")) == set(names)
    assert set(names) <= set(manager.search(""))


def test_concurrent_saves_publish_one_complete_transcript(tmp_path, monkeypatch):
    """Two saves of one conversation never share a temporary inode.

    The writes are forced to overlap: the first starts its JSON, waits for the
    second to publish, then finishes. With a predictable `<file>.tmp` both
    saves open the same inode, the second renames it over the live file and the
    first finishes writing into the published file, leaving invalid JSON while
    one of the two saves reports failure. With `mkstemp` each save owns its
    temporary file and the last complete write wins.
    """
    history_dir = str(tmp_path)
    first = FileHistoryManager(history_dir)
    second = FileHistoryManager(history_dir)
    first.update("shared", [ModelRequest(parts=[UserPromptPart(content="first")])])
    second.update("shared", [ModelRequest(parts=[UserPromptPart(content="second")])])

    first_started = threading.Event()
    second_written = threading.Event()

    def coordinated_dump(data, stream, **kwargs):
        if data[0]["parts"][0]["content"] == "first":
            stream.write('{"writer": "first"')
            stream.flush()
            first_started.set()
            if not second_written.wait(timeout=5):
                raise RuntimeError("the second save never wrote")
            stream.write("}")
        else:
            if not first_started.wait(timeout=5):
                raise RuntimeError("the first save never started")
            stream.write('{"writer": "second"}')
            stream.flush()
            second_written.set()

    monkeypatch.setattr(history_module.json, "dump", coordinated_dump)

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(first.save, "shared", False),
            pool.submit(second.save, "shared", False),
        ]
        for future in futures:
            future.result(timeout=10)

    with open(os.path.join(history_dir, "shared.json"), encoding="utf-8") as stream:
        assert json.load(stream) in ({"writer": "first"}, {"writer": "second"})
    assert not first.is_dirty("shared")
    assert not second.is_dirty("shared")
    assert not [name for name in os.listdir(history_dir) if name.endswith(".tmp")]


@pytest.mark.parametrize("name", [".", ".."])
def test_a_dot_segment_name_gets_no_backup(tmp_path, name):
    """`.json` appended to `.`/`..` is a harmless filename, but either one as a
    directory name would escape `backups/`, so no backup is written."""
    manager = FileHistoryManager(str(tmp_path))

    _save(manager, name)

    assert not (tmp_path / "backups").exists()


@pytest.mark.skipif(os.name != "posix", reason="symlinks need POSIX semantics")
def test_a_symlinked_backup_directory_is_refused(tmp_path):
    """The sanitized key is checked after resolving symlinks, so a link in
    `backups/` cannot redirect the write outside the history directory."""
    history_dir = tmp_path / "history"
    (history_dir / "backups").mkdir(parents=True)
    outside = tmp_path / "outside"
    outside.mkdir()
    os.symlink(str(outside), str(history_dir / "backups" / "hello"))

    manager = FileHistoryManager(str(history_dir))
    _save(manager, "hello")

    assert (history_dir / "hello.json").exists()
    assert os.listdir(outside) == []


def test_a_failed_replace_cleans_up_its_temporary_file(tmp_path, monkeypatch):
    """`mkstemp` leaves its file behind if the rename fails; the save removes
    it, keeps the entry dirty and reports failure."""
    manager = FileHistoryManager(str(tmp_path))
    manager.update("hello", [ModelRequest(parts=[UserPromptPart(content="hi")])])

    def fail_replace(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(history_module.os, "replace", fail_replace)

    manager.save("hello", write_backup=False)

    assert manager.is_dirty("hello")
    assert not (tmp_path / "hello.json").exists()
    assert not [name for name in os.listdir(tmp_path) if name.endswith(".tmp")]
