"""Concurrency check: concurrent speakers must not overlap.

Mirrors production: zrb fires Stop / PermissionRequest / Notification on a
thread pool as separate *processes*. They share only the lock file, so this
uses real subprocesses rather than threads or multiprocessing.

Run: python3 test_concurrency.py
"""

import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).parent
TRACE = Path("/tmp/zrb-concurrency-trace.log")
STUB = HERE / "_stub_backend.py"

# A backend that records when it started and finished, and takes long enough
# that any overlap is unmistakable.
STUB_CODE = '''
import sys, time
start = time.monotonic()
with open("/tmp/zrb-concurrency-trace.log", "a") as fh:
    fh.write(f"START {sys.argv[1]} {start:.4f}\\n")
    fh.flush()
time.sleep(0.5)
with open("/tmp/zrb-concurrency-trace.log", "a") as fh:
    fh.write(f"END   {sys.argv[1]} {time.monotonic():.4f}\\n")
    fh.flush()
'''


def main() -> int:
    TRACE.write_text("")
    STUB.write_text(STUB_CODE)

    env = dict(os.environ)
    env["ZRB_VOICE_BACKEND"] = "espeak-ng"
    # Point the speaker at our stub by shadowing espeak-ng on PATH.
    shim_dir = Path("/tmp/zrb-voice-shim")
    shim_dir.mkdir(exist_ok=True)
    shim = shim_dir / "espeak-ng"
    shim.write_text(
        f'#!/bin/sh\nexec {sys.executable} {STUB} "$@"\n'
    )
    shim.chmod(0o755)
    env["PATH"] = f"{shim_dir}:{env['PATH']}"

    procs = [
        subprocess.Popen(
            [sys.executable, str(HERE / "voice_speaker.py"), f"message-number-{i}"],
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        for i in range(3)
    ]
    start = time.monotonic()
    for p in procs:
        p.wait(timeout=60)
    elapsed = time.monotonic() - start

    events = [ln for ln in TRACE.read_text().splitlines() if ln.strip()]
    print("\n".join(events))
    print(f"\nwall time: {elapsed:.2f}s  (serialized ~1.5s / overlapped ~0.5s)")

    # Reconstruct: a START must never land between another START and its END.
    active = 0
    overlap = False
    for line in events:
        if line.startswith("START"):
            active += 1
            if active > 1:
                overlap = True
        else:
            active -= 1

    print(f"events: {len(events)} (expect 6)")
    print(f"overlap detected: {overlap}")

    STUB.unlink(missing_ok=True)
    shim.unlink(missing_ok=True)

    if overlap:
        print("FAIL: utterances overlapped -- the lock is not serializing")
        return 1
    if len(events) != 6:
        print("FAIL: not every speaker reached the backend")
        return 1
    print("PASS: all three utterances serialized, none overlapped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
