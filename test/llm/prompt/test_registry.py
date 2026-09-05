"""Public PromptRegistry behavior (ADR-0090 split from PromptManager)."""

from zrb.context.context import Context
from zrb.context.shared_context import SharedContext
from zrb.llm.prompt.manager import PromptManager, new_prompt
from zrb.llm.prompt.registry import PromptRegistry, prompt_registry


def _ctx() -> Context:
    """A real task context — what production hands the prompt system."""
    return Context(SharedContext(), "test", 0, "")


def _manager(registry):
    return PromptManager(
        prompt_registry=registry, include_sections=[], skill_manager=None
    )


def test_empty_by_default():
    assert PromptRegistry().get_prompts() == []


def test_defaults_to_fresh_isolated_registry():
    assert PromptRegistry() is not prompt_registry


def test_manager_defaults_to_global_registry(monkeypatch):
    reg = PromptRegistry()
    reg.append_prompt("Global Default")
    monkeypatch.setattr("zrb.llm.prompt.manager.default_prompt_registry", reg)
    manager = PromptManager(include_sections=[], skill_manager=None)
    assert manager.prompts == ["Global Default"]


def test_manager_exposes_its_registry():
    reg = PromptRegistry()
    assert _manager(reg).prompt_registry is reg


def test_registry_default_emitted_when_manager_defers():
    reg = PromptRegistry()
    reg.append_prompt("Registry Default")
    prompt = _manager(reg).compose_prompt()(_ctx())
    assert "Registry Default" in prompt


def test_set_prompts_deferred_awaits_query_time():
    calls = []

    def supplier():
        calls.append(1)
        return ["Late"]

    reg = PromptRegistry()
    reg.set_prompts(supplier)
    assert calls == []
    assert reg.get_prompts() == ["Late"]
    assert len(calls) == 1


def test_append_after_deferred_layers_on_default():
    reg = PromptRegistry()
    reg.set_prompts(lambda: ["A"])
    reg.append_prompt("B")
    assert reg.get_prompts() == ["A", "B"]


def test_append_layers_live_over_mutating_default():
    default = ["A"]
    reg = PromptRegistry(default=lambda: list(default))
    reg.append_prompt("B")
    assert reg.get_prompts() == ["A", "B"]
    default.append("C")
    assert reg.get_prompts() == ["A", "C", "B"]


def test_set_prompts_replaces_wholesale():
    reg = PromptRegistry()
    reg.set_prompts(["A"])
    reg.set_prompts(["B", "C"])
    assert reg.get_prompts() == ["B", "C"]


def test_prepend_prompt_runs_first():
    reg = PromptRegistry()
    reg.append_prompt("A")
    reg.prepend_prompt("B")
    assert reg.get_prompts() == ["B", "A"]


def test_remove_prompt_drops_exact_middleware():
    def first(ctx):
        return "First"

    def second(ctx):
        return "Second"

    reg = PromptRegistry()
    reg.append_prompt(first, second)
    reg.remove_prompt(first)
    assert reg.get_prompts() == [second]


def test_clear_returns_to_empty():
    reg = PromptRegistry()
    reg.append_prompt("A")
    reg.clear()
    assert reg.get_prompts() == []


def test_manager_accepts_deferred_prompts_callable():
    reg = PromptRegistry()
    manager = PromptManager(
        prompt_registry=reg,
        prompts=lambda: ["Deferred"],
        include_sections=[],
        skill_manager=None,
    )
    prompt = manager.compose_prompt()(_ctx())
    assert "Deferred" in prompt


def test_manager_resolves_callable_each_compose():
    state = {"calls": 0}

    def supplier():
        state["calls"] += 1
        return [f"Turn {state['calls']}"]

    reg = PromptRegistry()
    manager = PromptManager(
        prompt_registry=reg,
        prompts=supplier,
        include_sections=[],
        skill_manager=None,
    )
    assert "Turn 1" in manager.compose_prompt()(_ctx())
    assert "Turn 2" in manager.compose_prompt()(_ctx())
    assert state["calls"] == 2


def test_append_on_deferring_manager_layers_registry():
    reg = PromptRegistry()
    reg.append_prompt("R")
    manager = _manager(reg)
    manager.append_prompt("M")
    reg.append_prompt("R2")
    assert manager.prompts == ["R", "R2", "M"]


def test_manager_deltas_are_local_to_instance():
    reg = PromptRegistry()
    reg.append_prompt("R")
    manager = _manager(reg)
    manager.append_prompt("M")
    assert manager.prompts == ["R", "M"]
    assert reg.get_prompts() == ["R"]


def test_manager_append_prompt_preserves_order():
    reg = PromptRegistry()
    manager = _manager(reg)
    manager.append_prompt("First")
    manager.append_prompt(new_prompt("Middleware"))
    assert manager.prompts[0] == "First"
    assert manager.prompts[1](_ctx(), "", lambda c, p: p) == "\nMiddleware"


def test_reset_returns_to_registry_default():
    reg = PromptRegistry()
    reg.append_prompt("R")
    manager = _manager(reg)
    manager.append_prompt("M")
    manager.reset()
    assert manager.prompts == ["R"]


def test_remove_prompt_on_deferring_manager():
    reg = PromptRegistry()
    reg.append_prompt("M0", "M1")
    manager = _manager(reg)
    manager.remove_prompt("M0")
    assert manager.prompts == ["M1"]
