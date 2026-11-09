"""Recall by cue: a prompt that names a stored subject gets the claim back.

The hook is the reach nothing else made on the model's behalf — the core is what
a session starts with, `SearchMemory` is what it has to think to call, and a
prompt that names something stored is the cue both wait for.
"""

from unittest.mock import MagicMock

import pytest

from zrb.config.config import CFG
from zrb.llm.agent.run.hook_result_extractor import extract_additional_context
from zrb.llm.hook.builtin.memory_recall import (
    RECALL_LIMIT,
    build_recall_hook_config,
    create_recall_hook,
    recall_text,
    register_recall_hook,
)
from zrb.llm.hook.contracts.interface import HookContext
from zrb.llm.hook.contracts.types import HookEvent
from zrb.llm.hook.manager.manager import HookManager
from zrb.llm.memory import paths, store
from zrb.llm.memory.model import Fact
from zrb.llm.memory.search import RESULT_CONTRACT
from zrb.llm.prompt.memory_context import render_memory_block, shown_claim_ids


@pytest.fixture
def store_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(CFG, "LLM_MEMORY_DIR", str(tmp_path / "memory"), raising=False)
    monkeypatch.setattr(CFG, "LLM_MEMORY_ENABLED", True, raising=False)
    monkeypatch.setattr(CFG, "LLM_MEMORY_GIT_ENABLED", False, raising=False)
    monkeypatch.setattr(CFG, "LLM_MEMORY_LOCK_TIMEOUT", 5.0, raising=False)
    paths.ensure_store()
    return tmp_path / "memory"


def _save(**fields):
    fields.setdefault("kind", "fact")
    fields.setdefault("status", "active")
    fields.setdefault("updated", "2026-11-10T04:00:00")
    fields.setdefault("source", "user")
    store.save_fact(Fact(**fields))


def test_a_prompt_naming_a_stored_subject_recalls_its_claim(store_dir):
    _save(
        id="staging-ssh-port",
        claim="Staging SSH is on port 2222.",
        tags=["staging", "ssh"],
    )

    text = recall_text("how do I reach staging ssh?")

    assert "staging-ssh-port" in text
    assert "port 2222" in text
    # A recalled claim is a prompt as much as the user's words are: it says so.
    assert RESULT_CONTRACT in text


def test_a_body_mention_alone_is_not_a_cue(store_dir):
    """The body is evidence. Recall fires on what a claim is about."""
    _save(
        id="unrelated",
        claim="Something else entirely.",
        body="staging ssh is mentioned in passing here",
    )

    assert recall_text("how do I reach staging ssh?") == ""


def test_a_claim_the_conversation_already_showed_is_not_recalled(store_dir):
    """The core already carries a pinned claim; repeating it buys nothing."""
    _save(id="staging-ssh-port", claim="Staging SSH is on port 2222.", pin=True)
    render_memory_block()
    assert "staging-ssh-port" in shown_claim_ids()

    assert recall_text("how do I reach staging ssh?") == ""


def test_a_pinned_claim_is_not_recalled_before_the_block_is_written(store_dir):
    """The block is written after the hooks run, so a first turn has no `shown`.

    Asking the store what its core would say keeps the cue from offering a claim
    the block is about to state in the same turn.
    """
    _save(id="staging-ssh-port", claim="Staging SSH is on port 2222.", pin=True)

    assert recall_text("how do I reach staging ssh?") == ""


def test_a_recall_is_recorded_so_the_next_turn_does_not_repeat_it(store_dir):
    _save(id="staging-ssh-port", claim="Staging SSH is on port 2222.")
    render_memory_block()

    assert recall_text("how do I reach staging ssh?") != ""
    assert "staging-ssh-port" in shown_claim_ids()
    assert recall_text("how do I reach staging ssh?") == ""


def test_a_prompt_too_short_to_be_a_cue_recalls_nothing(store_dir):
    _save(id="staging-ssh-port", claim="Staging SSH is on port 2222.")

    assert recall_text("continue") == ""
    assert recall_text("yes please") == ""


def test_memory_off_recalls_nothing(store_dir, monkeypatch):
    _save(id="staging-ssh-port", claim="Staging SSH is on port 2222.")
    monkeypatch.setattr(CFG, "LLM_MEMORY_ENABLED", False, raising=False)

    assert recall_text("how do I reach staging ssh?") == ""


def test_at_most_three_claims_ride_along(store_dir):
    for index in range(6):
        _save(id=f"redis-note-{index}", claim="Redis is the cache.", tags=["redis"])

    text = recall_text("which redis setup do we use?")

    assert text.count("facts/redis-note-") == RECALL_LIMIT


@pytest.mark.asyncio
async def test_the_hook_hands_the_recall_over_as_additional_context(store_dir):
    _save(id="staging-ssh-port", claim="Staging SSH is on port 2222.")
    hook = create_recall_hook()

    result = await hook(
        HookContext(
            event=HookEvent.USER_PROMPT_SUBMIT,
            event_data={},
            prompt="how do I reach staging ssh?",
        )
    )

    assert "port 2222" in str(result.modifications["additionalContext"])


@pytest.mark.asyncio
async def test_a_prompt_with_nothing_to_recall_adds_nothing(store_dir):
    hook = create_recall_hook()

    result = await hook(
        HookContext(
            event=HookEvent.USER_PROMPT_SUBMIT,
            event_data={},
            prompt="continue",
        )
    )

    assert result.modifications == {}


@pytest.mark.asyncio
async def test_the_context_reaches_the_turn_through_the_manager(store_dir):
    """The manager is where a background hook's result goes missing.

    An `is_async` agent hook is spawned fire-and-forget and records no result, so
    the claim has to come back out of `execute_hooks`, not merely out of the
    callable — a hook that runs and loses its answer is worse than none, because
    it has already marked the claim as given.
    """
    _save(id="staging-ssh-port", claim="Staging SSH is on port 2222.")
    manager = HookManager()
    register_recall_hook(manager)

    results = await manager.execute_hooks(
        HookEvent.USER_PROMPT_SUBMIT, {}, prompt="how do I reach staging ssh?"
    )

    assert "port 2222" in (extract_additional_context(results) or "")


def test_the_recall_hook_runs_on_the_user_prompt():
    config = build_recall_hook_config()

    assert config.name == "memory-recall"
    assert config.events == [HookEvent.USER_PROMPT_SUBMIT]
    # Synchronous: an async agent hook is spawned fire-and-forget and records no
    # result, so the context it returns would never reach the prompt.
    assert config.is_async is False
    assert config.timeout is None


def test_the_recall_hook_registers_once_while_memory_is_on(monkeypatch):
    monkeypatch.setattr(CFG, "LLM_MEMORY_ENABLED", True, raising=False)
    manager = MagicMock()
    manager.registry.get_configs.return_value = {}
    manager.register_hook_config.return_value = MagicMock()

    register_recall_hook(manager)

    assert [
        call.args[0].name for call in manager.register_hook_config.call_args_list
    ] == ["memory-recall"]
    # Registered, then swapped for the callable that does the work: the config
    # names an `AgentHookConfig` for the manager's sake and builds no agent.
    assert manager.add_hook.call_args.args[2].name == "memory-recall"


def test_a_recall_hook_already_registered_is_not_registered_again(monkeypatch):
    """`register_hook_config` refuses a disabled config, not a duplicate one."""
    monkeypatch.setattr(CFG, "LLM_MEMORY_ENABLED", True, raising=False)
    manager = MagicMock()
    manager.registry.get_configs.return_value = {"memory-recall": MagicMock()}

    register_recall_hook(manager)

    manager.register_hook_config.assert_not_called()


def test_nothing_recalls_when_memory_is_off(monkeypatch):
    monkeypatch.setattr(CFG, "LLM_MEMORY_ENABLED", False, raising=False)
    manager = MagicMock()

    register_recall_hook(manager)

    manager.register_hook_config.assert_not_called()
