"""One heavy local model loads at a time, whichever feature asked for it.

Two of them can load in the same chat process: emotion2vec+ (dictation's tone)
and the local speech service (Pocket TTS). Each costs far more while it loads
than it keeps afterwards — measured on a 6.8 GB WSL2 machine, funasr reads a
1.1 GB checkpoint and then copies it into the model, so the process peaks at
2.9 GB and settles at 977 MB, and importing torch is another 517 MB. Two loads
at once add those peaks up, which can get the process OOM-killed.

Loading them one after another does not make either peak smaller. It stops two
spikes from stacking, which is what decides whether the process survives on a
machine with a few gigabytes.
"""

from __future__ import annotations

import threading
from collections.abc import Iterator
from contextlib import contextmanager

#: How long a load waits for the one in progress before it gives up. Giving up
#: fails this load rather than running it beside the other: two spikes stacked
#: is what the slot exists to prevent, and a load that wedges (a hung download,
#: a model that never returns) must not stall the other feature forever either.
WAIT_SECONDS = 120.0

_slot = threading.Lock()


class ModelLoadBusyError(RuntimeError):
    """Another model held the slot for longer than `WAIT_SECONDS`.

    A `RuntimeError`, so each caller already treats it as a load that failed:
    the tone is off for the session, a sentence goes unspoken and the next one
    tries again, hands-free dictation stops and says why.
    """


@contextmanager
def heavy_model_load(purpose: str) -> Iterator[None]:
    """Hold the slot every heavy local model load shares for the duration of
    the block, or raise `ModelLoadBusyError` naming *purpose* when another load
    keeps it past `WAIT_SECONDS`.

    The slot is a plain lock held only while a model loads, never while one is
    used, so two loaded models keep working side by side.
    """
    if not _slot.acquire(timeout=WAIT_SECONDS):
        raise ModelLoadBusyError(
            f"{purpose} was not loaded: another model has been loading for "
            f"{WAIT_SECONDS:g}s, and loading both at once could run this "
            "machine out of memory"
        )
    try:
        yield
    finally:
        _slot.release()
