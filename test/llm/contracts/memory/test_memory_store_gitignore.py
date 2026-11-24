"""The store's ignore file: a byte that will not decode must not fail a turn."""

import os

import pytest

from zrb.config.config import CFG
from zrb.llm.contracts.memory import paths


@pytest.fixture
def store_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(CFG, "LLM_MEMORY_DIR", str(tmp_path / "memory"), raising=False)
    monkeypatch.setattr(CFG, "LLM_MEMORY_CORE_MAX_CHARS", 4_000, raising=False)
    monkeypatch.setattr(CFG, "LLM_MEMORY_GIT_ENABLED", False, raising=False)
    monkeypatch.setattr(CFG, "LLM_MEMORY_LOCK_TIMEOUT", 5.0, raising=False)
    monkeypatch.setattr(CFG, "LLM_MEMORY_LOG_RETENTION_DAYS", 90, raising=False)
    paths.ensure_store()
    return tmp_path / "memory"


def test_an_undecodable_gitignore_does_not_take_the_store_down(store_dir):
    """An ignore file git accepts must not fail the turn that prepares the store.

    `UnicodeDecodeError` is a `ValueError`, not an `OSError`, so the guard that
    treats an unreadable `.gitignore` as "leave it be" misses these bytes. The
    file is left exactly as it was: its entries are the user's, and rewriting
    them from a half-decoded read would drop whichever ones did not decode.
    """
    path = os.path.join(str(store_dir), ".gitignore")
    with open(path, "wb") as f:
        f.write(b"secrets.md\n\xff\xfe\n")
    paths.ensure_store()
    with open(path, "rb") as f:
        assert f.read() == b"secrets.md\n\xff\xfe\n"
    assert os.path.isdir(paths.facts_dir())
