"""Unit tests for the EnvField config descriptor."""

import os

import pytest

from zrb.config.env_field import (
    EnvField,
    comma_join,
    comma_list,
    expanduser_path_list,
    json_dump,
    json_object,
    on_off,
    path_list,
    path_list_join,
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
    ITEMS = EnvField(path_list, serialize=path_list_join, default="")
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
    SECRET = EnvField(str, secret=True, default="")


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


def test_secret_flag_defaults_false_and_is_exposed(host, monkeypatch):
    cls = type(host)
    assert cls.PLAIN.secret is False
    assert cls.SECRET.secret is True
    # secret is display-only: it never changes how the value is read or written.
    monkeypatch.setenv("TESTCFG_SECRET", "top-secret")
    assert host.SECRET == "top-secret"


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


def test_path_list_round_trip(host, monkeypatch):
    sep = os.pathsep
    assert host.ITEMS == []
    monkeypatch.setenv("TESTCFG_ITEMS", f"a {sep}{sep} b{sep}")
    assert host.ITEMS == ["a", "b"]
    host.ITEMS = ["x", "y"]
    assert os.environ["TESTCFG_ITEMS"] == f"x{sep}y"


def test_path_list_splits_on_semicolon_on_windows(monkeypatch):
    monkeypatch.setattr(os, "pathsep", ";")
    assert path_list(r"C:\foo;D:\bar") == [r"C:\foo", r"D:\bar"]
    assert path_list("C:/foo; C:/bar ;") == ["C:/foo", "C:/bar"]
    # A colon is never a separator there, so drive letters survive.
    assert path_list(r"C:\foo") == [r"C:\foo"]
    assert path_list_join([r"C:\foo", r"D:\bar"]) == r"C:\foo;D:\bar"


def test_path_list_splits_on_colon_on_posix(monkeypatch):
    monkeypatch.setattr(os, "pathsep", ":")
    assert path_list("x:/tmp:/var") == ["x", "/tmp", "/var"]
    assert path_list("foo;bar") == ["foo;bar"]


def test_comma_list_round_trip(host, monkeypatch):
    assert host.CMDS == []
    monkeypatch.setenv("TESTCFG_CMDS", "/a, /b ,")
    assert host.CMDS == ["/a", "/b"]
    host.CMDS = ["/x", "/y"]
    assert os.environ["TESTCFG_CMDS"] == "/x,/y"


def test_a_string_is_stored_as_the_env_text_on_a_list_field(host):
    """A str assigned in code is the env text, so it must reach the field
    unjoined — `",".join` on a str iterates its characters."""
    host.CMDS = "/x, /y"
    assert os.environ["TESTCFG_CMDS"] == "/x, /y"
    assert host.CMDS == ["/x", "/y"]


def test_a_string_is_stored_as_the_env_text_on_a_path_list_field(host):
    sep = os.pathsep
    host.ITEMS = f"a{sep}b"
    assert os.environ["TESTCFG_ITEMS"] == f"a{sep}b"
    assert host.ITEMS == ["a", "b"]


def test_a_string_is_stored_as_the_env_text_on_a_bool_field(host):
    """A non-empty str is truthy, so serializing one through ``on_off`` would
    write "on" and turn "off" into True."""
    host.FLAG = "off"
    assert os.environ["TESTCFG_FLAG"] == "off"
    assert host.FLAG is False


def test_a_string_the_cast_rejects_is_refused(host):
    """The string is still validated, so a bad one fails loudly instead of
    being written and read back as something else."""
    with pytest.raises(ValueError, match="is not valid"):
        host.PLAIN = "not-a-number"
    assert "TESTCFG_PLAIN" not in os.environ


def test_a_non_string_that_reads_back_differently_is_refused(host):
    """The round-trip guard still covers every non-str value: a tuple
    serializes to the field's env form but does not read back as itself."""
    with pytest.raises(ValueError, match="round-trip"):
        host.CMDS = ("/x", "/y")
    assert "TESTCFG_CMDS" not in os.environ


def test_expanduser_path_list_expands_home():
    result = expanduser_path_list(f"~/a {os.pathsep} ~/b")
    assert result == [os.path.expanduser("~/a"), os.path.expanduser("~/b")]
    assert expanduser_path_list("") == []


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


def test_convert_applies_cast_then_transform(host, monkeypatch):
    """`convert` is the assignment path's read: cast, then transform.

    A caller converting a string in order to assign it (e.g. `/set`) must get
    what the next read returns, not the bare cast (round-5 review).
    """
    monkeypatch.setenv("TESTCFG_TRANSFORMED", "7")
    assert _Host.TRANSFORMED.convert("7", host) == 14


def test_convert_propagates_a_bad_cast_instead_of_the_fallback(host):
    """`fallback` is for reads; a caller validating a value must see the error.

    Returning the fallback would let `/set` report success for a value the field
    never accepted.
    """
    with pytest.raises(ValueError):
        _Host.FALLBACK_INT.convert("not-a-number", host)


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


def test_json_object_parses_an_object_of_strings_keeping_its_order():
    assert json_object('{"b": "B", "a": 1}') == {"b": "B", "a": "1"}
    assert list(json_object('{"z": "", "a": ""}')) == ["z", "a"]
    assert json_object("  ") == {}


def test_json_object_refuses_anything_but_an_object():
    with pytest.raises(ValueError, match="JSON object"):
        json_object('["a"]')


def test_json_dump_writes_what_json_object_reads():
    value = {"Read": "Membaca berkas.", "*": "Pakai {tool}."}
    assert json_object(json_dump(value)) == value
