"""The speech lock file defaults into the user's own directory, not the shared
temp dir where another local user could plant the path."""

import os

from zrb.config.config import Config


def _use_home(monkeypatch, home) -> None:
    # `expanduser` reads HOME on POSIX and USERPROFILE on Windows.
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))


def test_the_speech_lock_file_defaults_into_the_users_own_directory(
    monkeypatch, tmp_path
):
    monkeypatch.delenv("ZRB_LLM_SPEECH_LOCK_FILE", raising=False)
    _use_home(monkeypatch, tmp_path)
    cfg = Config()

    assert cfg.LLM_SPEECH_LOCK_FILE == os.path.join(
        str(tmp_path), f".{cfg.ROOT_GROUP_NAME}", "llm-speech", "speech.lock"
    )


def test_the_speech_lock_file_default_follows_the_root_group_name(
    monkeypatch, tmp_path
):
    monkeypatch.delenv("ZRB_LLM_SPEECH_LOCK_FILE", raising=False)
    monkeypatch.setenv("ZRB_ROOT_GROUP_NAME", "myapp")
    _use_home(monkeypatch, tmp_path)

    assert Config().LLM_SPEECH_LOCK_FILE == os.path.join(
        str(tmp_path), ".myapp", "llm-speech", "speech.lock"
    )


def test_the_speech_lock_file_env_override_still_wins(monkeypatch, tmp_path):
    custom = str(tmp_path / "custom.lock")
    monkeypatch.setenv("ZRB_LLM_SPEECH_LOCK_FILE", custom)

    assert Config().LLM_SPEECH_LOCK_FILE == custom
