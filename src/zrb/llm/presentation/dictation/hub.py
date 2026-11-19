"""Hugging Face model files, taken from the local cache before the Hub.

`hf_hub_download` and `snapshot_download` ask the Hub whether a cached copy
changed on every call, a round trip on every start, and with no network they
wait for it to time out. A model is pinned once it is cached, so the cache
answers first and the Hub only fills it.
"""

from __future__ import annotations

from collections.abc import Callable


def get_hub_path(download: Callable[..., str], *args: str) -> str:
    """The local path *download* (`hf_hub_download` or `snapshot_download`)
    gives for *args*: the cached copy when there is one, without asking the
    Hub; else a download."""
    try:
        return download(*args, local_files_only=True)
    except OSError:
        # `LocalEntryNotFoundError`, an `OSError`: nothing cached yet.
        return download(*args)
