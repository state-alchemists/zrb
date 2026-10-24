"""A cut wakes the waits that were already waiting, and only those.

The generation is what keeps a keypress from moving the wrong command: it is
read when a shell starts waiting, and a cut that predates it must not satisfy
that shell.
"""

import asyncio

import pytest

from zrb.llm.shell_cut import (
    ShellCutSignal,
    current_shell_cut_signal,
    signal_for_run,
)


@pytest.mark.asyncio
async def test_a_cut_wakes_a_wait_that_started_before_it():
    signal = ShellCutSignal()
    waiter = asyncio.ensure_future(signal.wait_for_cut(signal.generation))
    await asyncio.sleep(0.01)

    signal.cut()

    await asyncio.wait_for(waiter, 1)


@pytest.mark.asyncio
async def test_a_cut_from_before_the_wait_does_not_wake_it():
    """The keypress arrived during an earlier tool call: this command was not
    running then, so nothing about it should move."""
    signal = ShellCutSignal()
    signal.cut()

    waiter = asyncio.ensure_future(signal.wait_for_cut(signal.generation))
    done, _ = await asyncio.wait({waiter}, timeout=0.05)

    assert not done
    waiter.cancel()


@pytest.mark.asyncio
async def test_every_wait_registered_before_one_cut_wakes():
    """Two commands may run in parallel; the user's key moves both."""
    signal = ShellCutSignal()
    generation = signal.generation
    waiters = [
        asyncio.ensure_future(signal.wait_for_cut(generation)) for _ in range(3)
    ]
    await asyncio.sleep(0.01)

    signal.cut()

    for waiter in waiters:
        await asyncio.wait_for(waiter, 1)


@pytest.mark.asyncio
async def test_a_wait_registered_after_a_cut_waits_for_the_next_one():
    signal = ShellCutSignal()
    signal.cut()
    waiter = asyncio.ensure_future(signal.wait_for_cut(signal.generation))
    await asyncio.sleep(0.01)
    assert not waiter.done()

    signal.cut()

    await asyncio.wait_for(waiter, 1)


def test_each_cut_advances_the_generation():
    signal = ShellCutSignal()

    signal.cut()
    signal.cut()

    assert signal.generation == 2


def test_a_nested_run_shares_its_parents_signal():
    """A sub-agent runs inside the turn the user is steering, so a `Shell` it
    starts must be reachable by the same key."""
    parent = ShellCutSignal()
    token = current_shell_cut_signal.set(parent)
    try:
        assert signal_for_run() is parent
    finally:
        current_shell_cut_signal.reset(token)


def test_a_top_level_run_mints_its_own_signal():
    assert current_shell_cut_signal.get() is None
    first = signal_for_run()
    second = signal_for_run()

    assert isinstance(first, ShellCutSignal)
    assert first is not second
