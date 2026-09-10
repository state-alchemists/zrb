from zrb.context.any_context import AnyContext
from zrb.context.context import Context
from zrb.context.shared_context import SharedContext
from zrb.llm.prompt.live_context_providers import LiveContextProviders


def _ctx() -> Context:
    """A real task context — what production hands the prompt system."""
    return Context(SharedContext(), "test", 0, "")


def test_add_provider_then_render():
    providers = LiveContextProviders()
    providers.add_provider("sprint", lambda ctx: "Active sprint: 42")
    assert providers.render(_ctx()) == ["Active sprint: 42"]


def test_add_provider_replaces_same_name():
    providers = LiveContextProviders()
    providers.add_provider("sprint", lambda ctx: "first")
    providers.add_provider("sprint", lambda ctx: "second")
    assert providers.render(_ctx()) == ["second"]


def test_remove_provider_drops_it():
    providers = LiveContextProviders()
    providers.add_provider("sprint", lambda ctx: "42")
    providers.remove_provider("sprint")
    assert providers.render(_ctx()) == []


def test_remove_provider_missing_name_is_a_no_op():
    providers = LiveContextProviders()
    providers.remove_provider("missing")
    assert providers.get_providers() == []


def test_set_providers_replaces_wholesale():
    providers = LiveContextProviders()
    providers.add_provider("old", lambda ctx: "old")
    providers.set_providers([("new", lambda ctx: "new")])
    assert providers.render(_ctx()) == ["new"]


def test_get_providers_returns_pairs_in_registration_order():
    def a(ctx: AnyContext):
        return "a"

    def b(ctx: AnyContext):
        return "b"

    providers = LiveContextProviders()
    providers.add_provider("a", a)
    providers.add_provider("b", b)
    assert providers.get_providers() == [("a", a), ("b", b)]


def test_render_skips_empty_output():
    providers = LiveContextProviders()
    providers.add_provider("empty", lambda ctx: "")
    providers.add_provider("none", lambda ctx: None)
    providers.add_provider("real", lambda ctx: "value")
    assert providers.render(_ctx()) == ["value"]


def test_render_swallows_a_raising_provider():
    providers = LiveContextProviders()

    def flaky(ctx):
        raise RuntimeError("boom")

    providers.add_provider("flaky", flaky)
    providers.add_provider("ok", lambda ctx: "still here")
    assert providers.render(_ctx()) == ["still here"]
