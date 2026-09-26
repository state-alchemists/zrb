"""Guards against constructor surface drift (R8-adjacent).

Three axes, all on the same problem: a task subclass re-declares and forwards
its parent's `__init__` parameters by hand, and nothing else checks the copy.

- *Count* — `PARAM_BUDGETS` caps how wide a constructor may get.
- *Order* — `LLMTask.__init__` and `LLMChatTask.__init__` share ~50 parameters
  that must stay in the same relative order, so muscle memory built on one
  transfers to the other, and the same docstring text unless the meaning
  genuinely differs.
- *Fidelity* — a parameter a subclass forwards must carry its parent's
  annotation (`test_subclasses_do_not_narrow_an_inherited_parameter_type`), and
  a parameter it does not forward must be a recorded decision, not an
  oversight (`test_subclasses_forward_every_parent_parameter_or_say_why`).

The bug class the fidelity pair catches: a docstring promising *"Every
parameter `X` accepts is also accepted here"* over a signature that quietly
drops nine of them, so a task can declare a readiness check it will never
configure or monitor.

`BaseUI` is the other host measured here; its UI-backend settings route
through `UIConfig` rather than its own signature.
"""

import ast
import inspect
import re
import textwrap
from typing import Unpack, get_origin

from zrb.llm.task.chat.task import LLMChatTask
from zrb.llm.task.llm_task import LLMTask
from zrb.llm.ui.base.ui import BaseUI
from zrb.task.base.base_task import BaseTask
from zrb.task.base_trigger import BaseTrigger
from zrb.task.cmd_task import CmdTask
from zrb.task.http_check import HttpCheck
from zrb.task.rsync_task import RsyncTask
from zrb.task.scaffolder import Scaffolder
from zrb.task.scheduler import Scheduler
from zrb.task.tcp_check import TcpCheck

# Max __init__ parameters per class. Lower these as the surface shrinks; a
# raise needs a one-line reason in the same diff, like the facade budgets.
# These are ceilings that only ever go DOWN. Pinned to the exact current count,
# not the count plus headroom: a budget with slack silently absorbs the next few
# additions, which is the drift this file exists to make visible. Lowering one
# needs nothing but the diff that earns it; RAISING one needs an ADR saying why
# the surface genuinely grew, not a comment on the line.
#
# Note what the numbers are *not*: 20 of `LLMChatTask`'s and `LLMTask`'s params
# are `BaseTask`'s, re-declared on purpose so the signature documents itself
# instead of hiding behind `**kwargs` — `PARENT_OF` and `INTENTIONAL_OMISSIONS`
# below exist to keep exactly those in sync. The number worth driving down is
# the rest.
#
# ADR-0090/0091 (R12) records the `llm_config` split these numbers reflect.
PARAM_BUDGETS = {
    LLMChatTask: 40,
    LLMTask: 30,
    BaseUI: 15,
}

# Every task class that re-declares another's parameters, mapped to the parent
# it copies from — the one its docstring names, which is not always the direct
# base (`Scheduler` promises parity with `BaseTrigger`, `RsyncTask` with
# `CmdTask`).
# Task classes that re-declare a parent's parameters by hand, mapped to that
# parent. Empty: every task class forwards through `**kwargs: Unpack[...]`
# instead, so the two fidelity tests below have nothing to compare. The rule
# holds for whatever lands here next.
PARENT_OF: dict[type, type] = {}

# Task classes that forward through `**kwargs: Unpack[...]`, mapped to the
# class whose parameters flow through. Their shared set is declared once in
# `task/base/params.py`, so nothing here can drift out of sync with it; what a
# subclass excludes is a narrower `TypedDict` plus a runtime guard in that
# module, not an entry here.
FORWARDS_TO = {
    LLMTask: BaseTask,
    LLMChatTask: BaseTask,
    CmdTask: BaseTask,
    RsyncTask: CmdTask,
    Scaffolder: BaseTask,
    Scheduler: BaseTrigger,
    BaseTrigger: BaseTask,
    HttpCheck: BaseTask,
    TcpCheck: BaseTask,
}

# (subclass, parameter) -> why this subclass deliberately does not forward it.
# Omitting a parent parameter is a legitimate design choice; omitting one by
# accident is the bug. An entry here is the difference, and it must be matched
# by the class's own docstring naming the same exclusion.
INTENTIONAL_OMISSIONS = {
    "action": "subclasses supply their own action; BaseTask's docstring says so",
}


def _params(cls) -> list[str]:
    return [p for p in inspect.signature(cls.__init__).parameters if p != "self"]


def _declared_params(cls) -> dict[str, tuple[str | None, str | None]]:
    """`cls.__init__`'s parameters as `{name: (annotation source, default source)}`.

    Read from the AST rather than `inspect.signature`: `llm/task/llm_task.py`
    and `llm/task/chat/task.py` carry `from __future__ import annotations`
    while `task/base/base_task.py` does not, so at runtime one side's
    annotations are strings and the other's are type objects, and every shared
    parameter on those two classes compares unequal. Source text is also what
    a reviewer reads in the diff.
    """
    func = ast.parse(textwrap.dedent(inspect.getsource(cls.__init__))).body[0]
    assert isinstance(func, ast.FunctionDef)
    args = func.args
    positional = args.args[1:]  # drop `self`
    defaults = (
        [None] * (len(positional) - len(args.defaults))
        + list(args.defaults)
        + list(args.kw_defaults)
    )
    return {
        arg.arg: (
            ast.unparse(arg.annotation) if arg.annotation is not None else None,
            ast.unparse(default) if default is not None else None,
        )
        for arg, default in zip(positional + args.kwonlyargs, defaults)
    }


def _omission_reason(cls, param: str) -> str | None:
    return INTENTIONAL_OMISSIONS.get((cls, param)) or INTENTIONAL_OMISSIONS.get(param)


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
    `sandbox`/`yolo` cluster once had."""
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


# Shared LLMTask/LLMChatTask parameters whose meaning differs between a
# one-shot run and an interactive session.
SHARED_PARAM_DOCS_THAT_DIFFER = {
    "active_skills": "pre-activated per task vs. per session",
    "approval_channel": "without one, LLMTask denies; chat asks through its UI",
    "attachment": "chat attaches to the initial message only",
    "custom_model_names": "chat offers them through the model picker",
    "hook_manager": "chat defaults to a fresh manager per run",
    "message": "chat's message is optional and precedes user input",
    "ui": "chat takes a ready-made UI to drive the session",
}


def _documented_params(cls) -> dict[str, str]:
    """`{name: description}` from the `Args:` block of `cls.__init__`'s docstring."""
    documented: dict[str, str] = {}
    current = None
    for line in (inspect.getdoc(cls.__init__) or "").splitlines():
        match = re.match(r"    (\w+): (.*)", line)
        if match:
            current = match.group(1)
            documented[current] = match.group(2)
        elif current and line.startswith("        "):
            documented[current] += " " + line.strip()
        else:
            current = None
    return documented


def test_the_two_task_classes_document_shared_parameters_identically():
    llm_task_docs = _documented_params(LLMTask)
    chat_task_docs = _documented_params(LLMChatTask)
    drifted = sorted(
        name
        for name in set(llm_task_docs) & set(chat_task_docs)
        if llm_task_docs[name] != chat_task_docs[name]
        and name not in SHARED_PARAM_DOCS_THAT_DIFFER
    )
    assert not drifted, (
        "LLMTask and LLMChatTask document these shared parameters differently. "
        "Copy one wording to both, or add the name to "
        f"SHARED_PARAM_DOCS_THAT_DIFFER with the reason: {drifted}"
    )


def test_subclasses_do_not_narrow_an_inherited_parameter_type():
    """A forwarded parameter must carry its parent's annotation verbatim.

    Narrowing is a promise the subclass cannot keep: `BaseTask` treats
    `readiness_timeout=None` as "use the default" and coerces it in the
    property getter, so a subclass annotating plain `int` rejects — at type
    check time only — a value the constructor it forwards to accepts.
    """
    narrowed = []
    for cls, parent in PARENT_OF.items():
        child_params, parent_params = _declared_params(cls), _declared_params(parent)
        for name, (parent_annotation, _) in parent_params.items():
            if name not in child_params:
                continue  # absence is the other test's business
            child_annotation = child_params[name][0]
            if child_annotation != parent_annotation:
                narrowed.append(
                    f"  {cls.__name__}.{name}: {child_annotation!r} "
                    f"(does not match {parent.__name__}: {parent_annotation!r})"
                )
    assert not narrowed, (
        "Constructor parameter(s) drifted from the parent they forward to. "
        "Copy the parent's annotation verbatim; if the parent's own type is "
        "wrong, fix it there so every subclass inherits the correction:\n"
        + "\n".join(narrowed)
    )


def test_subclasses_forward_every_parent_parameter_or_say_why():
    """A parent parameter a subclass does not forward must be a decision.

    Not forwarding one is often right — a readiness check has no business
    accepting `readiness_check`. Dropping one by accident is the bug. An
    `INTENTIONAL_OMISSIONS` entry is what separates the two, and the class
    docstring has to name the same exclusion.
    """
    unexplained = []
    for cls, parent in PARENT_OF.items():
        child_params = _declared_params(cls)
        for name in _declared_params(parent):
            if name in child_params or _omission_reason(cls, name):
                continue
            unexplained.append(f"  {cls.__name__} drops {parent.__name__}.{name}")
    assert not unexplained, (
        "Constructor(s) silently drop a parameter of the class they forward "
        "to. Either forward it, or add an INTENTIONAL_OMISSIONS entry here "
        "with the reason and name the same exclusion in the class "
        "docstring:\n" + "\n".join(unexplained)
    )


def test_task_subclasses_forward_rather_than_re_declare():
    """A task subclass must not re-declare a parameter it only forwards.

    Each copied name, type and default is a place the parent and child can
    disagree, and a parameter added to `BaseTask` has to be written into every
    subclass that copies it. `**kwargs: Unpack[BaseTaskParams]` carries the
    set instead, and pyright still completes and checks every name at the call
    site — its language server offers all 35 keywords at `CmdTask(` and the 14
    `HttpCheck` accepts at `HttpCheck(`.

    Shadowing a parent parameter — a different default or a narrower type — is
    a decision, so it needs an entry below with its reason; a copy that just
    restates the parent is not.
    """
    deliberate_shadowing: dict[tuple[type, str], str] = {
        (LLMChatTask, "retries"): (
            "a chat turn is interactive; a silent retry would replay the "
            "user's message, so the default drops from BaseTask's 2 to 0"
        ),
    }
    copies = []
    for cls, parent in FORWARDS_TO.items():
        child_params = _declared_params(cls)
        for name in _declared_params(parent):
            if name == "name":
                continue  # every task constructor takes its own `name`
            if name in child_params and (cls, name) not in deliberate_shadowing:
                copies.append(f"  {cls.__name__} re-declares {parent.__name__}.{name}")
    assert not copies, (
        "Constructor(s) re-declare a parameter they only forward. Drop it from "
        "the signature — `**kwargs: Unpack[...]` already carries it — or, if "
        "the subclass genuinely needs a different default or type, add a "
        "`deliberate_shadowing` entry here with the reason:\n" + "\n".join(copies)
    )


def _is_unpack(annotation: object) -> bool:
    """Whether `annotation` is `Unpack[...]`.

    An annotation is source text in a module with
    `from __future__ import annotations` and a typing object otherwise.
    `repr` is not common ground between the two: CPython renders the object
    as `*X` before 3.12 and as `typing.Unpack[X]` from 3.12 on.
    """
    if isinstance(annotation, str):
        return annotation.lstrip().startswith("Unpack[")
    return get_origin(annotation) is Unpack


def test_every_forwarding_subclass_declares_unpacked_kwargs():
    """The other half of the rule above: forwarding must actually happen.

    Without this, deleting a parameter from a signature and forgetting the
    `**kwargs` passes the re-declaration test while silently dropping the
    parameter from the public API.
    """
    missing = []
    for cls in FORWARDS_TO:
        params = inspect.signature(cls.__init__).parameters
        annotations = getattr(cls.__init__, "__annotations__", {})
        if not any(
            p.kind is inspect.Parameter.VAR_KEYWORD and _is_unpack(annotations.get(n))
            for n, p in params.items()
        ):
            missing.append(cls.__name__)
    assert not missing, (
        "Class(es) listed in FORWARDS_TO no longer declare "
        f"`**kwargs: Unpack[...]`, so their parent's parameters are gone from "
        f"the public API rather than forwarded: {missing}"
    )
