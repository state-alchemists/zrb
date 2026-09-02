"""Guards against constructor-parameter-count drift (R8-adjacent, Phase 5).

`LLMTask.__init__` and `LLMChatTask.__init__` share ~50 parameters that must
stay in the same relative order (`test_the_two_task_classes_agree_on_their_shared_parameters`)
so muscle memory built on one transfers to the other; a name present in both
signatures but reordered relative to the other is exactly the drift this file
exists to catch. `BaseUI` is the other host measured here — see
plan/05-constructor-surface.md for the Phase 5 migration that shrank it from
34 parameters to 15 by routing UI-backend settings through `UIConfig`.
"""

import inspect

from zrb.llm.task.chat.task import LLMChatTask
from zrb.llm.task.llm_task import LLMTask
from zrb.llm.ui.base.ui import BaseUI

# Max __init__ parameters per class. Lower these as the surface shrinks; a
# raise needs a one-line reason in the same diff, like the facade budgets.
PARAM_BUDGETS = {
    # Phase 6 (ADR-0090/0091, R12): removed the single `llm_config` param,
    # added the two task-level hooks it used to carry (`model_getter`,
    # `model_renderer`) as direct constructor slots — net +1.
    LLMChatTask: 71,
    LLMTask: 53,
    BaseUI: 15,
}


def _params(cls) -> list[str]:
    return [p for p in inspect.signature(cls.__init__).parameters if p != "self"]


def test_constructor_parameter_counts_stay_within_budget():
    over_budget = {}
    for cls, budget in PARAM_BUDGETS.items():
        actual = len(_params(cls))
        if actual > budget:
            over_budget[cls.__qualname__] = (actual, budget)
    assert not over_budget, (
        "Constructor(s) grew past their parameter budget — either the growth "
        "is real new surface (bump PARAM_BUDGETS here, with a reason) or it "
        f"should be collapsed into an existing config object: {over_budget}"
    )


def test_the_two_task_classes_agree_on_their_shared_parameters():
    """A name that appears in both `LLMTask.__init__` and
    `LLMChatTask.__init__` must sit in the same relative order in both — the
    drift `hook_manager` and the `ui`/`approval_channel`/`permissions`/
    `sandbox`/`yolo` cluster had before Phase 5."""
    llm_task_params = _params(LLMTask)
    chat_task_params = _params(LLMChatTask)
    shared = set(llm_task_params) & set(chat_task_params)

    ordered_in_llm_task = [p for p in llm_task_params if p in shared]
    ordered_in_chat_task = [p for p in chat_task_params if p in shared]

    assert ordered_in_llm_task == ordered_in_chat_task, (
        "LLMTask and LLMChatTask disagree on the relative order of their "
        f"shared constructor parameters.\nLLMTask order:     {ordered_in_llm_task}\n"
        f"LLMChatTask order: {ordered_in_chat_task}"
    )
