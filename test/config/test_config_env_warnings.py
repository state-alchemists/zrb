from zrb.config.config import Config
from zrb.config.env_field import EnvField
from zrb.config.retired import RETIRED_SETTINGS


def test_a_near_miss_of_a_setting_is_reported_with_the_setting(monkeypatch):
    monkeypatch.setenv("ZRB_LLM_DICTATION_BARGEIN_ENABLED", "on")
    assert Config().get_mistyped_env_keys()["ZRB_LLM_DICTATION_BARGEIN_ENABLED"] == (
        "ZRB_LLM_DICTATION_BARGE_IN_ENABLED"
    )


def test_a_projects_own_variable_is_not_called_a_typo(monkeypatch):
    monkeypatch.setenv("ZRB_USE_BORG_BUILTIN_WORKFLOW", "1")
    assert "ZRB_USE_BORG_BUILTIN_WORKFLOW" not in Config().get_mistyped_env_keys()


def test_a_real_setting_and_its_old_alias_are_not_typos(monkeypatch):
    monkeypatch.setenv("ZRB_LLM_MODEL", "openai:gpt-4o")
    mistyped = Config().get_mistyped_env_keys()
    assert "ZRB_LLM_MODEL" not in mistyped


def test_only_variables_under_the_prefix_are_checked(monkeypatch):
    monkeypatch.setenv("_ZRB_ENV_PREFIX", "ACME")
    monkeypatch.setenv("ZRB_LLM_MODELL", "x")
    monkeypatch.setenv("ACME_LLM_MODELL", "x")
    assert Config().get_mistyped_env_keys() == {"ACME_LLM_MODELL": "ACME_LLM_MODEL"}


def test_a_retired_setting_names_the_one_that_replaced_it(monkeypatch):
    monkeypatch.setenv("ZRB_LLM_VOICE_MODE", "openai")
    cfg = Config()
    assert cfg.get_retired_env_keys()["ZRB_LLM_VOICE_MODE"] == (
        "ZRB_LLM_DICTATION_BACKEND"
    )
    assert "ZRB_LLM_VOICE_MODE" not in cfg.get_mistyped_env_keys()


def test_a_retired_setting_with_no_replacement_says_why(monkeypatch):
    monkeypatch.setenv("ZRB_LLM_VOICE_ENABLED", "on")
    assert "/voice" in Config().get_retired_env_keys()["ZRB_LLM_VOICE_ENABLED"]


def test_every_replacement_is_a_setting_and_no_retired_name_is_read_again():
    cfg = Config()
    for name, instead in RETIRED_SETTINGS.items():
        assert not hasattr(type(cfg), name), f"{name} is read again"
        if instead.isupper() and " " not in instead:
            assert isinstance(getattr(type(cfg), instead, None), EnvField), instead
