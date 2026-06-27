#!/usr/bin/env python3
"""Print full backtraces from a core dump (portable postmortem triage).

Runs gdb in batch mode to dump every thread's stack, registers, and loaded
shared libraries — the first thing you want from a native crash (segfault,
SIGABRT, exit 139). READ-ONLY: it only inspects the core and binary.

Usage:
  python coredump-bt.py <binary> <corefile>     explicit binary + core
  python coredump-bt.py --systemd <exe|pid>     let systemd-coredump locate it

Examples:
  python coredump-bt.py ./myapp /var/lib/systemd/coredump/core.myapp.1234
  python coredump-bt.py --systemd myapp

Tip: build with -g. If symbols were stripped, install the matching debuginfo
package so frames resolve to file:line instead of ??.
"""

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# Batch commands shared by both modes; all-thread backtrace is the payload.
_GDB_BATCH = [
    "-batch",
    "-ex",
    "set pagination off",
    "-ex",
    "thread apply all bt full",
    "-ex",
    "echo \\n==== registers (crashing thread) ====\\n",
    "-ex",
    "info registers",
    "-ex",
    "echo \\n==== shared libraries ====\\n",
    "-ex",
    "info sharedlibrary",
]

_HELP = (
    "usage:\n"
    "  coredump-bt.py <binary> <corefile>     explicit binary + core\n"
    "  coredump-bt.py --systemd <exe|pid>     let systemd-coredump locate it"
)

_READING = """
==== reading it ====
- Frame #0 of the crashing thread is where it died; walk UP to the last frame
  in YOUR code -- that line is the suspect.
- `thread apply all bt`: two threads each blocked acquiring a lock == deadlock.
- Frames showing ?? mean missing symbols -- install the matching debuginfo
  package and re-run.
- Go: prefer `dlv core <binary> <core>`. Python: `gdb python <core>` then `py-bt`.
"""


def _run(cmd):
    """Run a command with inherited stdout (stream gdb output); return rc."""
    try:
        return subprocess.run(cmd, text=True).returncode
    except (FileNotFoundError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


def _capture(cmd):
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True)
    except (FileNotFoundError, OSError) as exc:
        return 1, "", str(exc)
    return proc.returncode, proc.stdout, proc.stderr


def _run_systemd(match):
    if shutil.which("coredumpctl") is None:
        print(
            "error: coredumpctl not found (systemd-coredump not installed)",
            file=sys.stderr,
        )
        return 2
    rc, info, err = _capture(["coredumpctl", "info", match])
    if rc != 0:
        print(f"error: coredumpctl info failed: {err.strip()}", file=sys.stderr)
        return 1
    print("===== coredumpctl info =====")
    summary_keys = ("Signal", "Executable", "Command Line", "Timestamp", "Storage")
    exe = ""
    for line in info.splitlines():
        stripped = line.strip()
        if any(stripped.startswith(k) for k in summary_keys):
            print(stripped)
        if stripped.startswith("Executable:"):
            exe = stripped.split(":", 1)[1].strip()
    if not exe:
        print(
            "error: could not determine executable from coredumpctl info",
            file=sys.stderr,
        )
        return 1

    fd, core = tempfile.mkstemp(suffix=".core")
    os.close(fd)
    try:
        if _run(["coredumpctl", "dump", match, f"--output={core}"]) != 0:
            print("error: coredumpctl dump failed", file=sys.stderr)
            return 1
        print(f"\n===== gdb {exe} <core> — all-thread backtrace =====")
        rc = _run(["gdb", exe, core, *_GDB_BATCH])
    finally:
        try:
            os.unlink(core)
        except OSError:
            pass
    print(_READING)
    return rc


def _run_explicit(binary, core):
    if shutil.which("gdb") is None:
        print("error: gdb not found on PATH (install gdb)", file=sys.stderr)
        return 2
    if not Path(binary).is_file():
        print(f"error: binary not found: {binary}", file=sys.stderr)
        return 2
    if not Path(core).is_file():
        print(f"error: core file not found: {core}", file=sys.stderr)
        return 2
    print(f"===== gdb {binary} {core} — all-thread backtrace =====")
    rc = _run(["gdb", binary, core, *_GDB_BATCH])
    print(_READING)
    return rc


def main(argv):
    if not argv or argv[0] in ("-h", "--help"):
        print(_HELP, file=sys.stderr)
        return 2
    if argv[0] == "--systemd":
        if len(argv) < 2:
            print(_HELP, file=sys.stderr)
            return 2
        return _run_systemd(argv[1])
    if len(argv) < 2:
        print(_HELP, file=sys.stderr)
        return 2
    return _run_explicit(argv[0], argv[1])


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
