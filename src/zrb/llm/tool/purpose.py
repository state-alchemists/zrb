"""The ``purpose`` argument a tool call carries, in one place.

A listener hears a short line when a tool starts. A call's own ``purpose`` is
the best of those lines — it says what the call is *for*, which a tool name and
its arguments only imply — and `zrb.llm.speech.progress` speaks it in preference
to the tool's phrase.

**No tool body reads it.** It is not a parameter to the work, it is the spoken
frame around it: the narrator reads it from the call's arguments before the
tool runs, so a declaration is the whole implementation.

A tool that acts declares one through `requires_purpose`, so the model must
write the line. A tool that does not act declares it too, with a default: the
description below is a standing instruction, and a model that reads it fills the
argument on every call — including on a lookup, where the tool never asked. A
schema that leaves it out turns that instruction into a validation error instead
of the work: on 2026-11-12, 7 of the 13 tool errors in 517 calls were exactly
`extra_forbidden` on `purpose`, 5 of them `SearchSkill`'s, and each one cost a
retried round plus a full context re-send. `zrb.llm.speech.progress` speaks the
line whenever a call carries one, so declaring it on a tool that does not act
adds nothing a listener hears and removes what the model cannot say.

The wording lives here rather than beside each tool because it is one contract
read at one place: it is folded into every declaring tool's schema, so editing
it changes what the model is asked for everywhere at once. Which tools must
declare one is
`test_every_tool_outside_the_harness_says_what_the_call_is_for` in
`test/llm/test_common_tools.py`.
"""

from __future__ import annotations

import inspect
from typing import Annotated, Callable, TypeVar

from pydantic import Field

Purpose = Annotated[
    str,
    Field(
        description=(
            "Always fill this: one short phrase saying what this call is FOR, "
            "read aloud to a user who is listening in place of the tool's "
            "generic line. Give the intent, not the arguments — 'Refactoring "
            "LLMTask into a package', never 'editing llmtask.py', and never the "
            "tool's name."
        )
    ),
]


_Tool = TypeVar("_Tool", bound=Callable[..., object])


def requires_purpose(fn: _Tool) -> _Tool:
    """Make ``purpose`` required in the schema a model reads.

    A keyword with a default is an invitation to skip it, and a skipped
    ``purpose`` is narrated as "Editing llmtask.py." — true of every call and
    of none. pydantic-ai builds a tool's schema from `inspect.signature`, so
    moving the parameter first without a default is enough: the model must
    write the line, while a Python caller (a test, another tool) may still
    leave it out, because nothing in the body reads it.

    A function that does not take ``purpose``, or takes it already required, is
    returned unchanged.
    """
    signature = inspect.signature(fn)
    purpose = signature.parameters.get("purpose")
    if purpose is None or purpose.default is inspect.Parameter.empty:
        return fn
    required = purpose.replace(default=inspect.Parameter.empty)
    others = [p for p in signature.parameters.values() if p.name != "purpose"]
    setattr(fn, "__signature__", signature.replace(parameters=[required, *others]))
    return fn
