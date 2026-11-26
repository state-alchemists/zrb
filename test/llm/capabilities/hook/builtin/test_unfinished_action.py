"""The gate that will not let a turn end on a promise it never kept.

The first two sentences below are the closing lines of one real session
(2026-11-26 19:36 and 19:37); each was followed by no tool call, five unanswered
review findings, and a person asking why the work had not started. The gate
reads the closing message, quotes the claim back, and extends the turn once.
"""

from unittest.mock import MagicMock, patch

import pytest

from zrb.llm.capabilities.hook.builtin.unfinished_action import (
    build_unfinished_action_hook_config,
    create_unfinished_action_hook,
    register_unfinished_action_hook,
    unfinished_claim,
)
from zrb.llm.capabilities.hook.contracts.interface import HookContext, HookResult
from zrb.llm.capabilities.hook.contracts.types import HookEvent
from zrb.llm.capabilities.hook.manager.manager import HookManager

_FIXING = (
    "<spoken>All six came back requesting changes. Two are holes my own changes "
    "opened, and I am fixing all ten before asking for another review.</spoken>"
)
_STARTING = (
    "<spoken>Nothing blocks it. I am starting with the two security regressions, "
    "#1070 and #1072.</spoken>"
)


def _is_block(result: HookResult) -> bool:
    return result.modifications.get("decision") == "block"


async def _run(
    hook,
    message: str | None,
    turn_id: str = "turn-1",
    nested_run: bool = False,
    stop_hook_active: bool = False,
) -> HookResult:
    context = HookContext(
        event=HookEvent.STOP,
        event_data={
            "turn_id": turn_id,
            "run_scope": "run-1",
            "nested_run": nested_run,
        },
        stop_hook_active=stop_hook_active,
        last_assistant_message=message,
    )
    return await hook(context)


@pytest.mark.parametrize("message", [_FIXING, _STARTING])
def test_the_closing_that_started_nothing_blocks_the_turn(message):
    result = unfinished_claim(message)
    assert result is not None
    assert "I am" in result


@pytest.mark.parametrize(
    "message",
    [
        # A report of work already done.
        "Six pull requests are open, #1070 to #1075.",
        # A decision the human has to make.
        "Which ADR number should I take, 0146 or 0148?",
        # Offers and closings name no work in progress.
        "I'll be here when you come back.",
        "I'll review the diffs when you hand them over.",
        "I'm done for tonight.",
        "I'm happy to split that into two PRs if you prefer.",
        # A negation is the opposite of a claim.
        "I am not fixing #1074 tonight.",
    ],
)
def test_a_report_a_question_or_an_offer_is_not_a_claim(message):
    assert unfinished_claim(message) is None


@pytest.mark.parametrize(
    "message",
    [
        "I am deleting the stale file now.",
        "I am removing the regression.",
        "I am installing the dependency.",
        "I am working on #1072.",
        "I am going to roll back the commit.",
    ],
)
def test_the_verbs_the_work_actually_uses_are_claims(message):
    """The list is the tool-and-workflow vocabulary, not a sample of it."""
    assert unfinished_claim(message) is not None


def test_an_immediate_intention_is_a_claim():
    assert unfinished_claim("I'm going to fix the loader guard next.") == (
        "I'm going to fix"
    )


@pytest.mark.asyncio
async def test_the_gate_blocks_once_per_turn():
    hook = create_unfinished_action_hook()
    first = await _run(hook, _FIXING, turn_id="turn-1")
    second = await _run(hook, _FIXING, turn_id="turn-1", stop_hook_active=True)
    assert _is_block(first)
    assert not _is_block(second)


@pytest.mark.asyncio
async def test_a_later_turn_is_judged_on_its_own():
    hook = create_unfinished_action_hook()
    await _run(hook, _FIXING, turn_id="turn-1")
    await _run(hook, _FIXING, turn_id="turn-1", stop_hook_active=True)
    assert _is_block(await _run(hook, _STARTING, turn_id="turn-2"))


@pytest.mark.asyncio
async def test_the_block_reason_quotes_the_claim_back():
    result = await _run(create_unfinished_action_hook(), _STARTING)
    reason = result.modifications["reason"]
    assert isinstance(reason, str)
    assert "I am starting" in reason
    assert "nothing after that sentence" in reason


@pytest.mark.asyncio
async def test_a_claim_is_judged_even_when_the_turn_already_did_work():
    """The claim is about the present, and the turn ends there.

    A turn that edited files and closed with "I am fixing the remaining issue"
    has an issue left and no turn left to fix it in. The gate does not read the
    turn's earlier tool calls on purpose: a sentence that says work is happening
    is judged when the turn stops, whatever ran before it.
    """
    result = await _run(
        create_unfinished_action_hook(),
        "The edits to `chat_api_route.py` are in. I am fixing the remaining "
        "issue now.",
    )
    assert _is_block(result)


@pytest.mark.asyncio
async def test_a_subagent_run_is_left_to_its_caller():
    result = await _run(create_unfinished_action_hook(), _FIXING, nested_run=True)
    assert not _is_block(result)
    assert "sub-agent" in (result.output or "")


@pytest.mark.asyncio
async def test_a_turn_with_no_message_is_not_judged():
    assert not _is_block(await _run(create_unfinished_action_hook(), None))


def test_the_config_is_a_stop_hook_with_no_model_behind_it():
    config = build_unfinished_action_hook_config()
    assert config.name == "unfinished-action"
    assert config.events == [HookEvent.STOP]
    assert config.is_async is False


@pytest.mark.asyncio
async def test_registration_is_switched_by_the_config_flag():
    manager = HookManager(search_dirs=[])
    with patch("zrb.llm.capabilities.hook.builtin.unfinished_action.CFG") as cfg:
        cfg.LLM_UNFINISHED_ACTION_ENABLED = False
        register_unfinished_action_hook(manager)
    assert "unfinished-action" not in manager.registry.get_configs()

    manager = HookManager(search_dirs=[])
    with patch("zrb.llm.capabilities.hook.builtin.unfinished_action.CFG") as cfg:
        cfg.LLM_UNFINISHED_ACTION_ENABLED = True
        register_unfinished_action_hook(manager)
    assert "unfinished-action" in manager.registry.get_configs()


@pytest.mark.asyncio
async def test_a_registered_gate_blocks_the_real_stop_event():
    manager = HookManager(search_dirs=[])
    with patch("zrb.llm.capabilities.hook.builtin.unfinished_action.CFG") as cfg:
        cfg.LLM_UNFINISHED_ACTION_ENABLED = True
        register_unfinished_action_hook(manager)
    results = await manager.execute_hooks(
        HookEvent.STOP,
        {"turn_id": "turn-1", "run_scope": "run-1", "nested_run": False},
        last_assistant_message=_STARTING,
    )
    blocked = [result for result in results if result.blocked]
    assert blocked, results
    assert blocked[0].decision == "block"


def test_registering_twice_keeps_one_gate():
    """A manager whose search dirs change re-scans without clearing its registry."""
    manager = HookManager(search_dirs=[])
    with patch("zrb.llm.capabilities.hook.builtin.unfinished_action.CFG") as cfg:
        cfg.LLM_UNFINISHED_ACTION_ENABLED = True
        register_unfinished_action_hook(manager)
        register_unfinished_action_hook(manager)
    hooks = manager.registry.get_hooks(HookEvent.STOP)
    assert len(hooks) == 1
