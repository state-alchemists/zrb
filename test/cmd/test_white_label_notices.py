"""Runtime notices name the CLI by its configured name, not by "zrb".

zrb is white-labelable (`docs/advanced-topics/white-labeling.md`): a
distribution sets `ENV_PREFIX` and `ROOT_GROUP_NAME` and ships as `acme`. A
notice that hardcodes `[zrb]` tells that user about a program they do not have,
and a remedy that says ``zrb <task>`` names a command they cannot type.
"""

import asyncio
import os

import pytest

from zrb.cmd.command import run_command, wait_for_exit_and_drain
from zrb.config.config import CFG
from zrb.config.helper import get_windows_posix_shell
from zrb.group.group import Group
from zrb.group.task_diagnostics import find_task_diagnostics
from zrb.task.base.base_task import BaseTask

_BASH = get_windows_posix_shell() or "bash"


@pytest.fixture
def brand(monkeypatch):
    """A white-labeled CLI, the way its `__main__.py` sets it up."""
    monkeypatch.setattr(CFG, "ROOT_GROUP_NAME", "acme")
    return "acme"


@pytest.mark.asyncio
async def test_the_dropped_lines_notice_uses_the_configured_name(brand):
    printed = []

    await run_command(
        [_BASH, "-c", "printf 'a\\nb\\nc'"],
        max_output_line=2,
        print_method=lambda message, **kwargs: printed.append(message),
    )

    assert any(line.startswith("[acme] dropped") for line in printed)
    assert not any("[zrb] dropped" in line for line in printed)


@pytest.mark.skipif(os.name != "posix", reason="background shell syntax is POSIX-only")
@pytest.mark.asyncio
async def test_the_discarded_output_notice_uses_the_configured_name(brand):
    """A background child holding the pipe is still reported under the CLI's
    own name — the notice is zrb's, but the program the user runs is not."""
    process = await asyncio.create_subprocess_shell(
        "(sleep 1; echo LATE) &",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    notices = []

    async def drain(stream):
        return await stream.read()

    readers = asyncio.gather(drain(process.stdout), drain(process.stderr))

    await wait_for_exit_and_drain(
        process, readers, drain_grace=0.2, reporter=notices.append
    )

    assert any(note.startswith("[acme] output not fully captured") for note in notices)


def test_the_unregistered_task_remedy_names_the_configured_command(brand):
    """The remedy is a command line: it has to be one the user can type."""
    orphan = BaseTask(name="orphan")

    (diagnostic,) = find_task_diagnostics(
        [("init", "orphan", orphan)], Group(name="root"), []
    )

    assert "`acme orphan`" in diagnostic.detail
    assert "`zrb orphan`" not in diagnostic.detail


def test_the_default_name_is_unchanged():
    """No white label: the notices still say zrb, so nothing else shifts."""
    assert CFG.ROOT_GROUP_NAME == "zrb"
