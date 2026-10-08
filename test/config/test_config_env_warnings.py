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


def test_a_project_can_name_its_own_variable_as_exempt(monkeypatch):
    """A project's own variable is a 0.977 near-miss of a real setting
    (`ZRB_LLM_PLUGIN_DIR` for `ZRB_LLM_PLUGIN_DIRS`), and no cutoff can tell
    that from a typo — only the project knows which names are its own."""
    monkeypatch.setenv("ZRB_LLM_PLUGIN_DIR", "/opt/plugins")
    cfg = Config()
    assert cfg.get_mistyped_env_keys()["ZRB_LLM_PLUGIN_DIR"] == "ZRB_LLM_PLUGIN_DIRS"
    monkeypatch.delenv("ZRB_PROJECT_ENV_KEYS", raising=False)
    cfg.PROJECT_ENV_KEYS = ["LLM_PLUGIN_DIR"]
    assert "ZRB_LLM_PLUGIN_DIR" not in cfg.get_mistyped_env_keys()


def test_a_glob_exempts_a_projects_whole_sub_namespace(monkeypatch):
    """One entry covers a family: `ZRB_LLM_PROXY_SMALL_MODEL` is a 0.864
    near-miss of `ZRB_LLM_SMALL_MODEL` while unclaimed."""
    monkeypatch.setenv("ZRB_LLM_PROXY_SMALL_MODEL", "qwen3")
    monkeypatch.setenv("ZRB_LLM_PROXY_MODEL", "qwen3")
    cfg = Config()
    assert "ZRB_LLM_PROXY_SMALL_MODEL" in cfg.get_mistyped_env_keys()
    monkeypatch.setenv("ZRB_PROJECT_ENV_KEYS", "LLM_PROXY_*")
    mistyped = cfg.get_mistyped_env_keys()
    assert "ZRB_LLM_PROXY_SMALL_MODEL" not in mistyped
    assert "ZRB_LLM_PROXY_MODEL" not in mistyped


def test_an_exemption_leaves_the_rest_of_the_report_alone(monkeypatch):
    monkeypatch.setenv("ZRB_PROJECT_ENV_KEYS", "LLM_PROXY_*")
    monkeypatch.setenv("ZRB_LLM_PROXY_SMALL_MODEL", "qwen3")
    monkeypatch.setenv("ZRB_LLM_MODELL", "x")
    assert Config().get_mistyped_env_keys() == {"ZRB_LLM_MODELL": "ZRB_LLM_MODEL"}


def test_an_exempt_name_is_never_a_suggestion_target(monkeypatch):
    """Naming a variable subtracts it from the report; it must not add a
    project's name to the candidate pool, or the warning would tell a user to
    set a variable zrb does not read."""
    monkeypatch.setenv("ZRB_PROJECT_ENV_KEYS", "LLM_PLUGIN_DIR")
    monkeypatch.setenv("ZRB_LLM_PLUGIN_DIRX", "/tmp/plugins")
    assert Config().get_mistyped_env_keys() == {
        "ZRB_LLM_PLUGIN_DIRX": "ZRB_LLM_PLUGIN_DIRS"
    }


def test_a_project_may_reuse_a_name_zrb_retired(monkeypatch):
    monkeypatch.setenv("ZRB_PROJECT_ENV_KEYS", "LLM_VOICE_MODE")
    monkeypatch.setenv("ZRB_LLM_VOICE_MODE", "openai")
    cfg = Config()
    assert cfg.get_retired_env_keys() == {}
    assert "ZRB_LLM_VOICE_MODE" not in cfg.get_mistyped_env_keys()


def test_the_exemption_is_prefix_relative(monkeypatch):
    """Entries carry no prefix, so one list serves any prefix."""
    monkeypatch.setenv("_ZRB_ENV_PREFIX", "BANKAI")
    monkeypatch.setenv("ARASAKA_PROJECT_ENV_KEYS", "LLM_PROXY_*")
    monkeypatch.setenv("ARASAKA_LLM_PROXY_BASE_URL", "https://proxy.example/v1")
    assert Config().get_mistyped_env_keys() == {}


def test_the_exemption_is_settable_in_code(monkeypatch):
    """Either code form reaches the same env var: a list of names, or the
    comma string an env var would carry."""
    monkeypatch.delenv("ZRB_PROJECT_ENV_KEYS", raising=False)
    cfg = Config()
    cfg.PROJECT_ENV_KEYS = ["LLM_PLUGIN_DIR", "LLM_PROXY_*"]
    assert cfg.PROJECT_ENV_KEYS == ["LLM_PLUGIN_DIR", "LLM_PROXY_*"]
    cfg.PROJECT_ENV_KEYS = "LLM_PLUGIN_DIR,LLM_PROXY_*"
    assert cfg.PROJECT_ENV_KEYS == ["LLM_PLUGIN_DIR", "LLM_PROXY_*"]
