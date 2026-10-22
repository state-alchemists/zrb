"""create_yielding_argv: an agent's command loses to zrb for memory and CPU."""

import os
import subprocess
import sys

import pytest

from zrb.cmd import command
from zrb.cmd.command import create_yielding_argv


@pytest.mark.skipif(sys.platform != "linux", reason="/proc is Linux-only")
def test_the_command_is_the_oom_killers_first_pick_and_runs_niced():
    argv = ["sh", "-c", "cat /proc/self/oom_score_adj; nice"]

    out = subprocess.run(
        create_yielding_argv(argv), capture_output=True, text=True, check=True
    ).stdout.split()

    assert out == ["1000", str(min(os.nice(0) + 10, 19))]


def test_windows_runs_the_command_unchanged(monkeypatch):
    monkeypatch.setattr(command.os, "name", "nt")

    assert create_yielding_argv(["cmd", "/c", "dir"]) == ["cmd", "/c", "dir"]


def test_a_missing_program_is_left_to_fail_on_its_own():
    argv = ["no-such-program-xyz", "-c", "true"]

    assert create_yielding_argv(argv) == argv
