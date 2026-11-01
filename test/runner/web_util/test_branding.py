from unittest.mock import MagicMock

from zrb.runner.web_util.branding import get_web_jargon, get_web_title


def _root_group() -> MagicMock:
    group = MagicMock()
    group.name = "acme"
    group.description = "Acme tasks"
    return group


def test_title_is_the_configured_one(monkeypatch):
    monkeypatch.setenv("ZRB_WEB_TITLE", "Acme Console")
    assert get_web_title(_root_group()) == "Acme Console"


def test_a_blank_title_falls_back_to_the_root_group_name(monkeypatch):
    monkeypatch.setenv("ZRB_WEB_TITLE", "   ")
    assert get_web_title(_root_group()) == "acme"


def test_jargon_is_the_configured_one(monkeypatch):
    monkeypatch.setenv("ZRB_WEB_JARGON", "Ship it")
    assert get_web_jargon(_root_group()) == "Ship it"


def test_a_blank_jargon_falls_back_to_the_root_group_description(monkeypatch):
    monkeypatch.setenv("ZRB_WEB_JARGON", "  ")
    assert get_web_jargon(_root_group()) == "Acme tasks"
