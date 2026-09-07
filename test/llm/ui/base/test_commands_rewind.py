"""`/rewind` — snapshot listing, restore, and the unavailable path.

`MockUI` and the `ui` fixture come from `conftest.py`.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.mark.asyncio
async def test_handle_rewind_command_list(ui):
    snap = MagicMock()
    snap.sha = "1234567890"
    snap.timestamp = "2021-01-01"
    snap.label = "test"
    ui.snapshot_manager.list_snapshots.return_value = [snap]

    assert ui.handle_rewind_command("/rewind") is True
    # Listing happens in a background task (git subprocess off the UI thread)
    assert len(ui.background_tasks) == 1
    task = list(ui.background_tasks)[0]
    await task
    assert "12345678" in "".join(ui.outputs)


@pytest.mark.asyncio
async def test_handle_rewind_command_restore(ui):
    snap = MagicMock()
    snap.sha = "1234567890"
    snap.message_count = 5
    ui.snapshot_manager.list_snapshots.return_value = [snap]
    ui.snapshot_manager.restore_snapshot = AsyncMock(return_value=True)

    assert ui.handle_rewind_command("/rewind 1") is True
    # Restoration happens in a background task
    assert len(ui.background_tasks) == 1
    task = list(ui.background_tasks)[0]
    await task
    ui.snapshot_manager.restore_snapshot.assert_called_with(snap.sha)


def test_rewind_without_snapshots_warns_instead_of_reaching_the_model(ui, monkeypatch):
    """An unavailable command consumes its own input and says why (ADR-0093).

    `dispatch_command` forwards anything no handler claimed, so returning
    False here would send the literal text "/rewind" to the model.
    """
    monkeypatch.setenv("ZRB_LLM_ENABLE_REWIND", "off")
    ui.snapshot_manager = None

    assert ui.handle_rewind_command("/rewind") is True
    output = "".join(ui.outputs)
    assert "Rewind is not enabled" in output
    assert "ZRB_LLM_ENABLE_REWIND=on" in output
    assert not ui.background_tasks


def test_rewind_without_snapshots_still_ignores_other_input(ui):
    """The availability check sits after the token match, so input that is
    not a rewind command passes to the next handler."""
    ui.snapshot_manager = None
    assert ui.handle_rewind_command("what is a snapshot?") is False
    assert ui.outputs == []


def test_rewind_names_the_session_requirement_when_the_knob_is_already_on(
    ui, monkeypatch
):
    """`snapshot_manager` is also None when rewind is enabled but the session
    has no name or snapshot dir, where naming the knob would be a dead end."""
    monkeypatch.setenv("ZRB_LLM_ENABLE_REWIND", "on")
    ui.snapshot_manager = None

    assert ui.handle_rewind_command("/rewind") is True
    output = "".join(ui.outputs)
    assert "unavailable in this session" in output
    assert "ZRB_LLM_ENABLE_REWIND=on" not in output


def test_rewind_is_listed_in_help_even_without_snapshots(ui):
    """Help lists every command with a resolved alias (ADR-0093), so rewind
    is discoverable even though `LLM_ENABLE_REWIND` is off by default."""
    ui.snapshot_manager = None
    assert any("/rewind" in row for row in ui.get_help_text(80).splitlines())
