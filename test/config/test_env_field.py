"""Unit tests for the EnvField config descriptor."""

import os

import pytest

from zrb.config.env_field import (
    EnvField,
    colon_join,
    colon_list,
    comma_join,
    comma_list,
    expanduser_colon_list,
    on_off,
)
from zrb.util.string.conversion import to_boolean


class _Host:
    """Minimal host exposing the contract EnvField relies on."""

    ENV_PREFIX = "TESTCFG"
    ROOT_GROUP_NAME = "zrb"

    def __init__(self):
        self.DEFAULT_PLAIN = "7"

    PLAIN = EnvField(int, doc="plain int from DEFAULT_ fallback")
    ALIASED = EnvField(int, aliases=["NEW_NAME", "OLD_NAME"], default="0")
    ASYMMETRIC = EnvField(int, write_key="CANON_KEY", default="0")
    EXPLICIT_DEFAULT = EnvField(int, default="42")
    FACTORY = EnvField(str, default_factory=lambda host: f"dir-{host.ROOT_GROUP_NAME}")
    FLAG = EnvField(to_boolean, serialize=on_off, default="false")
    ITEMS = EnvField(colon_list, serialize=colon_join, default="")
    CMDS = EnvField(comma_list, serialize=comma_join, default="")
    NULLABLE = EnvField(str, nullable=True)


@pytest.fixture
def host(monkeypatch):
    for key in list(os.environ):
        if key.startswith("TESTCFG_"):
            monkeypatch.delenv(key, raising=False)
    return _Host()


def test_reads_default_from_host_attribute(host):
    assert host.PLAIN == 7


def test_explicit_default_used_when_unset(host):
    assert host.EXPLICIT_DEFAULT == 42


def test_default_factory_computed_from_host(host):
    assert host.FACTORY == "dir-zrb"


def test_default_factory_overridden_by_env(host, monkeypatch):
    monkeypatch.setenv("TESTCFG_FACTORY", "custom")
    assert host.FACTORY == "custom"


def test_env_overrides_default(host, monkeypatch):
    monkeypatch.setenv("TESTCFG_PLAIN", "99")
    assert host.PLAIN == 99


def test_alias_read_order(host, monkeypatch):
    monkeypatch.setenv("TESTCFG_OLD_NAME", "5")
    assert host.ALIASED == 5
    # First alias wins over the second.
    monkeypatch.setenv("TESTCFG_NEW_NAME", "8")
    assert host.ALIASED == 8


def test_setter_writes_attribute_name_by_default(host):
    host.PLAIN = 12
    assert os.environ["TESTCFG_PLAIN"] == "12"


def test_setter_honors_write_key(host):
    host.ASYMMETRIC = 3
    assert os.environ["TESTCFG_CANON_KEY"] == "3"


def test_bool_cast_and_on_off_serialize(host, monkeypatch):
    assert host.FLAG is False
    monkeypatch.setenv("TESTCFG_FLAG", "yes")
    assert host.FLAG is True
    # Setter serializes back to on/off, not "True"/"False".
    host.FLAG = True
    assert os.environ["TESTCFG_FLAG"] == "on"
    host.FLAG = False
    assert os.environ["TESTCFG_FLAG"] == "off"


def test_colon_list_round_trip(host, monkeypatch):
    assert host.ITEMS == []
    monkeypatch.setenv("TESTCFG_ITEMS", "a :: b:")
    assert host.ITEMS == ["a", "b"]
    host.ITEMS = ["x", "y"]
    assert os.environ["TESTCFG_ITEMS"] == "x:y"


def test_comma_list_round_trip(host, monkeypatch):
    assert host.CMDS == []
    monkeypatch.setenv("TESTCFG_CMDS", "/a, /b ,")
    assert host.CMDS == ["/a", "/b"]
    host.CMDS = ["/x", "/y"]
    assert os.environ["TESTCFG_CMDS"] == "/x,/y"


def test_expanduser_colon_list_expands_home():
    result = expanduser_colon_list("~/a : ~/b")
    assert result == [os.path.expanduser("~/a"), os.path.expanduser("~/b")]
    assert expanduser_colon_list("") == []


def test_nullable_reads_none_when_unset(host):
    assert host.NULLABLE is None


def test_nullable_set_value_then_clear(host):
    host.NULLABLE = "x"
    assert os.environ["TESTCFG_NULLABLE"] == "x"
    assert host.NULLABLE == "x"
    host.NULLABLE = None
    assert "TESTCFG_NULLABLE" not in os.environ
    assert host.NULLABLE is None


def test_class_access_returns_descriptor():
    assert isinstance(_Host.PLAIN, EnvField)


def test_doc_is_exposed():
    assert _Host.PLAIN.__doc__ == "plain int from DEFAULT_ fallback"
