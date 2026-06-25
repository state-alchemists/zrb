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
    FALLBACK_INT = EnvField(int, fallback=0, default="42")
    TRANSFORMED = EnvField(
        int,
        transform=lambda v, h: v * 2,
        default="5",
        doc="int doubled via transform",
    )
    BARE = EnvField(str, no_prefix=True, default="fallback")
    BARE_ALIASED = EnvField(
        str, no_prefix=True, aliases=["_INTERNAL_KEY"], write_key="_INTERNAL_KEY"
    )


@pytest.fixture
def host(monkeypatch):
    for key in list(os.environ):
        if key.startswith("TESTCFG_"):
            monkeypatch.delenv(key, raising=False)
    # Bare (no_prefix) keys used by the no_prefix tests.
    for key in ("BARE", "_INTERNAL_KEY"):
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


def test_empty_env_var_falls_back_to_default_for_typed_field(host, monkeypatch):
    """An explicitly empty env var must not crash a typed (non-nullable) cast."""
    monkeypatch.setenv("TESTCFG_PLAIN", "")
    # Without the guard this would raise ValueError from int("").
    assert host.PLAIN == 7
    monkeypatch.setenv("TESTCFG_EXPLICIT_DEFAULT", "")
    assert host.EXPLICIT_DEFAULT == 42


def test_empty_env_var_falls_back_to_default_for_bool_field(host, monkeypatch):
    monkeypatch.setenv("TESTCFG_FLAG", "")
    # Without the guard this would raise from to_boolean("").
    assert host.FLAG is False


def test_fallback_used_when_env_var_is_garbage(host, monkeypatch):
    monkeypatch.setenv("TESTCFG_FALLBACK_INT", "not-a-number")
    assert host.FALLBACK_INT == 0


def test_fallback_not_used_when_env_var_is_valid(host, monkeypatch):
    monkeypatch.setenv("TESTCFG_FALLBACK_INT", "99")
    assert host.FALLBACK_INT == 99


def test_fallback_not_used_when_env_var_is_unset(host):
    assert host.FALLBACK_INT == 42


def test_transform_applied_after_cast(host, monkeypatch):
    monkeypatch.setenv("TESTCFG_TRANSFORMED", "7")
    assert host.TRANSFORMED == 14


def test_transform_applied_to_default(host):
    assert host.TRANSFORMED == 10


def test_transform_receives_host_object(host, monkeypatch):
    # transform doubles the value; verify it's actually called.
    monkeypatch.setenv("TESTCFG_TRANSFORMED", "3")
    assert host.TRANSFORMED == 6


def test_no_prefix_reads_bare_env_name(host, monkeypatch):
    assert host.BARE == "fallback"
    # Read uses the bare name, NOT the prefixed one.
    monkeypatch.setenv("TESTCFG_BARE", "prefixed")
    assert host.BARE == "fallback"
    monkeypatch.setenv("BARE", "bare-value")
    assert host.BARE == "bare-value"


def test_no_prefix_writes_bare_env_name(host, monkeypatch):
    monkeypatch.delenv("BARE", raising=False)
    host.BARE = "written"
    assert os.environ["BARE"] == "written"
    assert "TESTCFG_BARE" not in os.environ


def test_no_prefix_honors_aliases_and_write_key(host, monkeypatch):
    monkeypatch.setenv("_INTERNAL_KEY", "internal")
    assert host.BARE_ALIASED == "internal"
    host.BARE_ALIASED = "set"
    assert os.environ["_INTERNAL_KEY"] == "set"


def test_env_key_respects_prefix_and_no_prefix():
    assert _Host.PLAIN.env_key("TESTCFG") == "TESTCFG_PLAIN"
    assert _Host.BARE.env_key("TESTCFG") == "BARE"
    assert _Host.BARE_ALIASED.env_key("TESTCFG") == "_INTERNAL_KEY"


def test_class_access_returns_descriptor():
    assert isinstance(_Host.PLAIN, EnvField)


def test_doc_is_exposed():
    assert _Host.PLAIN.__doc__ == "plain int from DEFAULT_ fallback"
