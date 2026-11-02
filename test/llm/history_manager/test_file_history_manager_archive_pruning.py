"""Verbatim archives are collected with the conversation that pointed at them.

An archive is the only copy of the text a summary dropped, so it is deleted only
when nothing refers to it any more — never merely because it is old, and never
while the summary that names it is still on disk.
"""

import os
import time

import pytest
from pydantic_ai.messages import ModelRequest, UserPromptPart

from zrb.llm.history_manager.file_history_manager import FileHistoryManager
from zrb.llm.summarizer.verbatim_archive import archive_lock_path, verbatim_archive_path

OLD = 40 * 24 * 60 * 60


@pytest.fixture
def history_dir(tmp_path):
    return tmp_path


@pytest.fixture
def retention():
    from unittest.mock import patch

    with patch("zrb.llm.history_manager.file_history_manager.CFG") as cfg:
        cfg.LLM_HISTORY_RETENTION = "30d"
        cfg.LLM_HISTORY_BACKUP_RETAIN = 0
        yield cfg


def _archive(history_dir, name: str, age_seconds: float = OLD) -> str:
    """An archive section written *age_seconds* ago, with its lock sidecar."""
    path = verbatim_archive_path(name, str(history_dir))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as stream:
        stream.write("## Compacted earlier — 1 message(s)\n")
    open(archive_lock_path(path), "w").close()
    stamp = time.time() - age_seconds
    os.utime(path, (stamp, stamp))
    return path


def _history(history_dir, name: str, body: str = "[]") -> str:
    path = os.path.join(str(history_dir), f"{name}.json")
    with open(path, "w", encoding="utf-8") as stream:
        stream.write(body)
    return path


def _backup(history_dir, base_name: str, body: str) -> str:
    """A retained timestamped backup, named the way `_get_backup_file_path`
    actually spells one: `<base>-YYYY-MM-DD-HH-MM-SS.json`, not a numbered
    `.json.N` suffix — it still ends in `.json`, like the live file."""
    path = os.path.join(str(history_dir), f"{base_name}-2020-01-01-00-00-00.json")
    with open(path, "w", encoding="utf-8") as stream:
        stream.write(body)
    return path


def _subagent_history(history_dir, agent_type: str, name: str, body: str) -> str:
    """A delegated transcript, which lives one level below the history root."""
    directory = os.path.join(str(history_dir), "subagent", agent_type)
    os.makedirs(directory, exist_ok=True)
    path = os.path.join(directory, f"{name}.json")
    with open(path, "w", encoding="utf-8") as stream:
        stream.write(body)
    return path


def _pointer_to(history_dir, name: str) -> str:
    """The archive pointer a summary carries, as the history file stores it."""
    path = verbatim_archive_path(name, str(history_dir))
    return f'["## Verbatim history archive", "Read `\\\\`{path}\\\\``"]'


def _save(manager: FileHistoryManager, name: str) -> None:
    manager.update(name, [ModelRequest(parts=[UserPromptPart(content="hi")])])
    manager.save(name, write_backup=False)


def test_an_archive_no_history_refers_to_is_pruned(history_dir, retention):
    """The conversation it belonged to is gone, so nothing can read it back."""
    path = _archive(history_dir, "orphan")
    _history(history_dir, "mine")

    _save(FileHistoryManager(str(history_dir)), "fresh-session")

    assert not os.path.exists(path)


def test_its_lock_sidecar_goes_with_it(history_dir, retention):
    path = _archive(history_dir, "orphan")

    _save(FileHistoryManager(str(history_dir)), "fresh-session")

    assert not os.path.exists(archive_lock_path(path))


def test_an_archive_a_summary_still_points_at_is_kept(history_dir, retention):
    """The pointer is the archive's only purpose: while it is on disk, the text
    behind it must stay readable."""
    path = _archive(history_dir, "kept")
    _history(history_dir, "mine", _pointer_to(history_dir, "kept"))

    _save(FileHistoryManager(str(history_dir)), "fresh-session")

    assert os.path.exists(path)


def test_a_recent_archive_is_kept_before_its_history_is_saved(history_dir, retention):
    """Compaction writes the archive, then the history; between the two nothing
    refers to it yet, and deleting it there would lose the only copy."""
    path = _archive(history_dir, "just-written", age_seconds=0)

    _save(FileHistoryManager(str(history_dir)), "fresh-session")

    assert os.path.exists(path)


def test_the_session_being_saved_keeps_its_archive(history_dir, retention):
    """Same window, from the other side: the save that triggers the prune may
    land before the file it saves mentions the archive."""
    path = _archive(history_dir, "in-flight")

    _save(FileHistoryManager(str(history_dir)), "in-flight")

    assert os.path.exists(path)


def test_retention_off_keeps_every_archive(history_dir, retention):
    """`LLM_HISTORY_RETENTION=0` means keep every history, so nothing that
    history might point at may be deleted either."""
    retention.LLM_HISTORY_RETENTION = "0"
    path = _archive(history_dir, "orphan")

    _save(FileHistoryManager(str(history_dir)), "fresh-session")

    assert os.path.exists(path)


def test_an_archive_named_only_by_a_retained_backup_is_kept(history_dir, retention):
    """The live history for a conversation can be gone — renamed, or itself
    already pruned — while a retained backup beside it still names the
    archive. `_references_named_in` reads every `.json` file in the directory,
    not just ones matching the live-file naming shape, so this already works;
    pinned here since a backup file ends in plain `.json` in this codebase,
    not the `.json.N` shape a reviewer once assumed it would."""
    path = _archive(history_dir, "kept")
    _backup(history_dir, "mine", _pointer_to(history_dir, "kept"))

    _save(FileHistoryManager(str(history_dir)), "fresh-session")

    assert os.path.exists(path)


def test_a_sub_agent_summary_keeps_its_archive(history_dir, retention):
    """A delegated transcript sits in `subagent/<agent-type>/` but writes into
    the same shared `verbatim/` directory, so a pruner that read only the root
    deleted an archive a sub-agent's summary still pointed at — silent loss of
    the only copy of what that summary dropped."""
    path = _archive(history_dir, "delegated")
    _subagent_history(
        history_dir,
        "generalist",
        "bold-arch-1234-sub-generalist-0000abcd",
        _pointer_to(history_dir, "delegated"),
    )

    _save(FileHistoryManager(str(history_dir)), "fresh-session")

    assert os.path.exists(path)


def test_a_sub_agent_archive_no_transcript_names_is_still_pruned(
    history_dir, retention
):
    """The sub-agent directories widen what counts as a reference, not what
    survives: an archive nothing names anywhere still goes."""
    path = _archive(history_dir, "forgotten")
    _subagent_history(
        history_dir, "generalist", "bold-arch-1234-sub-generalist-0000abcd", "[]"
    )

    _save(FileHistoryManager(str(history_dir)), "fresh-session")

    assert not os.path.exists(path)


def test_an_archive_for_a_session_name_with_spaces_is_kept(history_dir, retention):
    """`safe_segment` keeps a space from a session name, so the archive is
    literally named `verbatim/my session.md` -- the reference pattern used to
    exclude whitespace from the captured filename and never matched it."""
    path = verbatim_archive_path("my session", str(history_dir))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as stream:
        stream.write("## Compacted earlier — 1 message(s)\n")
    stamp = time.time() - OLD
    os.utime(path, (stamp, stamp))
    _history(history_dir, "mine", _pointer_to(history_dir, "my session"))

    _save(FileHistoryManager(str(history_dir)), "fresh-session")

    assert os.path.exists(path)


def _tool_results(history_dir, name: str, age_seconds: float = OLD) -> str:
    """A conversation's verbatim tool-result directory, written *age_seconds* ago."""
    directory = os.path.join(str(history_dir), "verbatim", f"{name}.tool-results")
    os.makedirs(directory, exist_ok=True)
    path = os.path.join(directory, "call-1.txt")
    with open(path, "w", encoding="utf-8") as stream:
        stream.write("the full tool output")
    stamp = time.time() - age_seconds
    os.utime(path, (stamp, stamp))
    os.utime(directory, (stamp, stamp))
    return directory


def _pointer_to_tool_results(history_dir, name: str) -> str:
    """The path a pruned result carries, as a transcript stores it."""
    directory = os.path.join(str(history_dir), "verbatim", f"{name}.tool-results")
    return f'["PRUNED TOOL RESULT: full output: `{directory}/call-1.txt`"]'


def test_an_orphan_tool_result_directory_is_pruned(history_dir, retention):
    """A result can be pruned long before its conversation compacts, so no
    archive is ever written for it. Retention must still reach the directory."""
    directory = _tool_results(history_dir, "never-compacted")
    _history(history_dir, "mine")

    _save(FileHistoryManager(str(history_dir)), "fresh-session")

    assert not os.path.exists(directory)


def test_a_tool_result_directory_a_transcript_points_at_is_kept(history_dir, retention):
    """The pointer is the only way back to the full output; it cannot outlive
    the file it names."""
    directory = _tool_results(history_dir, "still-pointed-at")
    _history(
        history_dir, "mine", _pointer_to_tool_results(history_dir, "still-pointed-at")
    )

    _save(FileHistoryManager(str(history_dir)), "fresh-session")

    assert os.path.exists(directory)
    assert os.path.exists(os.path.join(directory, "call-1.txt"))


def test_a_recent_tool_result_directory_is_kept(history_dir, retention):
    """Between the prune and the save that first names it, nothing points at it
    yet; age is what keeps that window safe."""
    directory = _tool_results(history_dir, "just-pruned", age_seconds=0)

    _save(FileHistoryManager(str(history_dir)), "fresh-session")

    assert os.path.exists(directory)


def test_the_session_being_saved_keeps_its_tool_results(history_dir, retention):
    """The save that triggers the prune may land before the file it saves
    mentions the pointer."""
    directory = _tool_results(history_dir, "in-flight")

    _save(FileHistoryManager(str(history_dir)), "in-flight")

    assert os.path.exists(directory)


def test_a_tool_result_directory_goes_with_its_archive(history_dir, retention):
    """The existing path still holds: once the archive is collected, the tool
    results it pointed at go with it."""
    archive = _archive(history_dir, "gone")
    directory = _tool_results(history_dir, "gone")

    _save(FileHistoryManager(str(history_dir)), "fresh-session")

    assert not os.path.exists(archive)
    assert not os.path.exists(directory)


def test_a_new_file_inside_an_old_directory_keeps_it(history_dir, retention):
    """A reused directory can keep an old mtime while a newly spilled result
    sits inside it; the newest child, not the directory, decides."""
    directory = _tool_results(history_dir, "reused")
    recent = os.path.join(directory, "call-2.txt")
    with open(recent, "w", encoding="utf-8") as stream:
        stream.write("a freshly spilled output")
    stamp = time.time() - OLD
    os.utime(directory, (stamp, stamp))

    _save(FileHistoryManager(str(history_dir)), "fresh-session")

    assert os.path.isdir(directory)
    assert os.path.exists(recent)


def test_an_archive_goes_but_a_referenced_tool_result_directory_stays(
    history_dir, retention
):
    """The directory can outlive the summary that named the archive: a pruned
    result in the kept tail still points at it after the summary stops naming
    `session.md`. Removing the archive must not take that pointer's target."""
    archive = _archive(history_dir, "outlived")
    directory = _tool_results(history_dir, "outlived")
    _history(history_dir, "mine", _pointer_to_tool_results(history_dir, "outlived"))

    _save(FileHistoryManager(str(history_dir)), "fresh-session")

    assert not os.path.exists(archive)
    assert os.path.isdir(directory)
    assert os.path.exists(os.path.join(directory, "call-1.txt"))
