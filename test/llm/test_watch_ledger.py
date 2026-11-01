"""The ledger of watches: what outlived a turn, and how it ended.

The file is written before the work starts and closed when it ends, so the
assertions here are about order, privacy and delivery — not about any tool.
"""

import json
import os
import stat
import sys

import pytest

from zrb.llm.watch import FINISHED, KILLED, RUNNING, WatchLedger


def _ledger(tmp_path, session: str = "s") -> WatchLedger:
    return WatchLedger(str(tmp_path), session)


def _rows(ledger: WatchLedger) -> list[dict]:
    with open(ledger.path, encoding="utf-8") as stream:
        return [json.loads(line) for line in stream.read().splitlines()]


def _rewrite_instance(ledger: WatchLedger, instance: str) -> int:
    """Rewrite every `opened` row as if another run of zrb had written it."""
    with open(ledger.path, encoding="utf-8") as stream:
        rows = [json.loads(line) for line in stream.read().splitlines()]
    for row in rows:
        if row.get("op") == "opened":
            row["instance"] = instance
    with open(ledger.path, "w", encoding="utf-8") as stream:
        for row in rows:
            stream.write(json.dumps(row, sort_keys=True) + "\n")
    return len(rows)


def test_a_watch_is_on_disk_before_the_work_starts(tmp_path):
    """`opened` is written first, so a crash still shows what was about to run."""
    ledger = _ledger(tmp_path)

    ledger.open("h1", kind="process", what="Running the tests")

    (row,) = _rows(ledger)
    assert row["op"] == "opened"
    assert row["id"] == "h1"
    assert row["what"] == "Running the tests"
    assert ledger.records()[0].state == RUNNING


@pytest.mark.skipif(
    sys.platform == "win32", reason="Windows offers no POSIX permission bits"
)
def test_the_ledger_is_readable_only_by_its_owner(tmp_path):
    """It holds command lines; it must not be world-readable."""
    ledger = _ledger(tmp_path)

    ledger.open("h1", kind="process", what="echo secret")

    mode = stat.S_IMODE(os.stat(ledger.path).st_mode)
    assert mode == 0o600


def test_a_finished_watch_is_unread_until_it_is_shown(tmp_path):
    ledger = _ledger(tmp_path)
    ledger.open("h1", kind="process", what="Running the tests")
    ledger.end("h1", 0)

    (record,) = ledger.unread()
    assert record.id == "h1"
    assert record.state == FINISHED
    assert record.exit_code == 0

    (line,) = ledger.render_lines()
    assert "exit 0" in line
    assert "Running the tests" in line
    assert ledger.unread() == []


def test_an_outcome_is_shown_once_and_never_again(tmp_path):
    """Delivery is the read: a second turn must not repeat the same line."""
    ledger = _ledger(tmp_path)
    ledger.open("h1", kind="process", what="Running the tests")
    ledger.end("h1", 0)

    ledger.render_lines()

    assert ledger.render_lines() == []


def test_a_killed_watch_does_not_read_as_success(tmp_path):
    ledger = _ledger(tmp_path)
    ledger.open("h1", kind="process", what="Waiting for a slot")
    ledger.end("h1", -9, killed=True)

    (record,) = ledger.unread()
    assert record.state == KILLED
    (line,) = ledger.render_lines()
    assert "killed" in line
    assert "exit 0" not in line


def test_a_watch_the_live_registry_still_reports_is_left_unread(tmp_path):
    """The block says each fact once: a live handle is already in the prompt."""
    ledger = _ledger(tmp_path)
    ledger.open("h1", kind="process", what="Running the tests")
    ledger.end("h1", 0)

    assert ledger.render_lines(skip={"h1"}) == []
    assert [record.id for record in ledger.unread()] == ["h1"]


def test_a_process_with_no_output_to_point_at_says_so(tmp_path):
    ledger = _ledger(tmp_path)
    ledger.open("h1", kind="process", what="Running the tests")
    ledger.end("h1", 0)

    (line,) = ledger.render_lines()
    assert "no longer held by this session" in line


def test_two_session_names_that_sanitise_alike_stay_apart(tmp_path):
    """`team/a` and `team_a` must not share a file and each other's watches."""
    first = _ledger(tmp_path, "team/a")
    second = _ledger(tmp_path, "team_a")

    first.open("h1", kind="process", what="The first session's secret")

    assert first.path != second.path
    assert second.records() == []


def test_a_row_left_by_a_dead_process_is_reported_lost(tmp_path):
    """`running` from another run of zrb means the ending was never seen."""
    ledger = _ledger(tmp_path)
    ledger.open("h1", kind="process", what="Killed with the process")
    foreign = _rewrite_instance(ledger, "someone-else")

    assert ledger.reconcile() == ["h1"]
    assert ledger.unread()[0].state == "lost"
    assert foreign


def test_a_running_row_from_this_process_is_left_alone(tmp_path):
    ledger = _ledger(tmp_path)
    ledger.open("h1", kind="process", what="Still running here")

    assert ledger.reconcile() == []
    assert ledger.unread() == []


def test_a_torn_line_costs_one_row_not_the_file(tmp_path):
    """A crash mid-append leaves half a line; the rest still reads."""
    ledger = _ledger(tmp_path)
    ledger.open("h1", kind="process", what="Running the tests")
    with open(ledger.path, "a", encoding="utf-8") as stream:
        stream.write('{"op": "opened", "id": "h2"')

    assert [record.id for record in ledger.records()] == ["h1"]


def test_compaction_keeps_only_watches_that_still_say_something(tmp_path):
    ledger = _ledger(tmp_path)
    ledger.open("done", kind="process", what="Already reported")
    ledger.end("done", 0)
    ledger.render_lines()
    ledger.open("live", kind="process", what="Still running")
    ledger.open("unread", kind="process", what="Just finished")
    ledger.end("unread", 1)

    ledger.compact()

    assert {record.id for record in ledger.records()} == {"live", "unread"}
    assert [record.id for record in ledger.unread()] == ["unread"]


def test_two_sessions_never_read_each_other(tmp_path):
    first = _ledger(tmp_path, "one")
    second = _ledger(tmp_path, "two")

    first.open("h1", kind="process", what="First session's work")

    assert first.path != second.path
    assert second.records() == []


def test_a_session_name_with_a_slash_is_still_a_safe_filename(tmp_path):
    ledger = _ledger(tmp_path, "web/chat:1")

    ledger.open("h1", kind="process", what="Something")

    assert os.path.dirname(ledger.path) == str(tmp_path)
    assert "/" not in os.path.basename(ledger.path)


@pytest.mark.skipif(
    sys.platform == "win32", reason="Windows offers no POSIX permission bits"
)
def test_an_existing_world_readable_ledger_is_tightened(tmp_path):
    """A restored or externally created file must not stay readable."""
    ledger = _ledger(tmp_path)
    ledger.open("h1", kind="process", what="Something private")
    os.chmod(ledger.path, 0o644)

    ledger.end("h1", 0)

    assert stat.S_IMODE(os.stat(ledger.path).st_mode) == 0o600


def test_a_long_description_is_shortened_rather_than_stored_whole(tmp_path):
    ledger = _ledger(tmp_path)

    ledger.open("h1", kind="process", what="x" * 400)

    assert len(ledger.records()[0].what) <= 120
