"""One heavy local model loads at a time, whichever feature asked for it.

Two of them can load in the same chat process: emotion2vec+ (dictation's tone)
and the local speech service (Pocket TTS). Each costs far more while it loads
than it keeps afterwards — measured on a 6.8 GB WSL2 machine, funasr reads a
1.1 GB checkpoint and then copies it into the model, so the process peaks at
2.9 GB and settles at 977 MB, and importing torch is another 517 MB. A session
that starts speech and dictation together used to run both loads at once, and
the two peaks added up: the chat was killed by the kernel's OOM killer at
3 GB of anonymous memory, four times in three days.

Loading them one after another does not make either peak smaller. It stops two
spikes from stacking, which is what decides whether the process survives on a
machine with a few gigabytes.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Iterator
from contextlib import contextmanager

logger = logging.getLogger(__name__)

#: How long a load waits for the one in progress before going ahead without
#: the slot. A load that wedges — a hung download, a model that never returns —
#: must not cost the other feature its model for the rest of the session.
WAIT_SECONDS = 120.0

_slot = threading.Lock()


@contextmanager
def heavy_model_load(purpose: str) -> Iterator[None]:
    """Hold the slot every heavy local model load shares for the duration of
    the block; *purpose* names the load in the log when the wait is given up on.

    The slot is a plain lock held only while a model loads, never while one is
    used, so two loaded models keep working side by side.
    """
    if not _slot.acquire(timeout=WAIT_SECONDS):
        logger.warning(
            f"Loading {purpose} without waiting for the model already loading: "
            f"{WAIT_SECONDS:g}s passed"
        )
        yield
        return
    try:
        yield
    finally:
        _slot.release()
