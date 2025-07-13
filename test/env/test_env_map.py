import os
from unittest import mock

from zrb.context.shared_context import SharedContext
from zrb.env.env_map import EnvMap


def test_env_map_dict():
    env_map = EnvMap(vars={"key1": "value1", "key2": "value2"})
    shared_ctx = SharedContext(env={})
    env_map.update_context(shared_ctx)
    assert shared_ctx.env["key1"] == "value1"
    assert shared_ctx.env["key2"] == "value2"


def test_env_map_callable():
    def get_vars(shared_ctx: SharedContext):
        return {"key1": "value1", "key2": "value2"}

    env_map = EnvMap(vars=get_vars)
    shared_ctx = SharedContext(env={})
    env_map.update_context(shared_ctx)
    assert shared_ctx.env["key1"] == "value1"
    assert shared_ctx.env["key2"] == "value2"


def test_env_map_link_to_os(monkeypatch):
    monkeypatch.setenv("MY_PREFIX_key1", "os_value1")
    env_map = EnvMap(
        vars={"key1": "value1", "key2": "value2"},
        link_to_os=True,
        os_prefix="MY_PREFIX",
    )
    shared_ctx = SharedContext(env={})
    env_map.update_context(shared_ctx)
    assert shared_ctx.env["key1"] == "os_value1"
    assert shared_ctx.env["key2"] == "value2"


def test_env_map_no_link_to_os(monkeypatch):
    monkeypatch.setenv("key1", "os_value1")
    env_map = EnvMap(vars={"key1": "value1", "key2": "value2"}, link_to_os=False)
    shared_ctx = SharedContext(env={})
    env_map.update_context(shared_ctx)
    assert shared_ctx.env["key1"] == "value1"
    assert shared_ctx.env["key2"] == "value2"


def test_env_map_auto_render(monkeypatch):
    env_map = EnvMap(vars={"key1": "{{'hello'}}", "key2": "value2"})
    shared_ctx = SharedContext(env={})
    with mock.patch.object(shared_ctx, "render", side_effect=lambda x: "hello" if x == "{{'hello'}}" else x):
        env_map.update_context(shared_ctx)
        assert shared_ctx.env["key1"] == "hello"
        assert shared_ctx.env["key2"] == "value2"
