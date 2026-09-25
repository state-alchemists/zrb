"""hold_file_lock: one holder at a time, across threads and processes, and
released by the OS when its holder dies."""

import subprocess
import sys
import threading
import time

import pytest

from zrb.util.file_lock import FileLockTimeout, hold_file_lock


def test_a_second_holder_in_another_thread_waits_for_the_first(tmp_path):
    path = str(tmp_path / "op.lock")
    held, order = threading.Event(), []

    def first():
        with hold_file_lock(path):
            held.set()
            time.sleep(0.3)
            order.append("first released")

    thread = threading.Thread(target=first)
    thread.start()
    held.wait(5)
    with hold_file_lock(path):
        order.append("second acquired")
    thread.join()

    assert order == ["first released", "second acquired"]


def test_a_holder_in_another_process_is_waited_for_and_released_when_killed(
    tmp_path,
):
    path = str(tmp_path / "op.lock")
    holder = subprocess.Popen(
        [
            sys.executable,
            "-c",
            "import sys, time\n"
            "from zrb.util.file_lock import hold_file_lock\n"
            "with hold_file_lock(sys.argv[1]):\n"
            "    print('held', flush=True)\n"
            "    time.sleep(60)\n",
            path,
        ],
        stdout=subprocess.PIPE,
        text=True,
    )
    assert holder.stdout.readline().strip() == "held"
    acquired = threading.Event()

    def second():
        with hold_file_lock(path):
            acquired.set()

    thread = threading.Thread(target=second, daemon=True)
    thread.start()

    assert not acquired.wait(0.3)  # the other process holds it
    holder.kill()  # dies holding it: nothing is left behind
    holder.wait()
    assert acquired.wait(15)


def test_a_wait_past_its_timeout_gives_up(tmp_path):
    path = str(tmp_path / "op.lock")
    held, release = threading.Event(), threading.Event()

    def holder():
        with hold_file_lock(path):
            held.set()
            release.wait(5)

    thread = threading.Thread(target=holder)
    thread.start()
    held.wait(5)
    started = time.monotonic()
    try:
        with pytest.raises(FileLockTimeout):
            with hold_file_lock(path, timeout=0.2):
                pass
    finally:
        release.set()
        thread.join()

    assert time.monotonic() - started < 2
