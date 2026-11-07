"""The ``purpose`` argument a tool call may carry, in one place.

A listener hears a short line when a tool starts. A call's own ``purpose`` is
the best of those lines — it says what the call is *for*, which a tool name and
its arguments only imply — and `zrb.llm.speech.progress` speaks it in preference
to the tool's phrase. Tools that take a while, or that change something the user
will notice, declare it; `ask_user_question` does not, because its question is
its purpose.

**No tool body reads it.** It is not a parameter to the work, it is the spoken
frame around it: the narrator reads it from the call's arguments before the
tool runs, so a declaration is the whole implementation.

The wording lives here rather than beside each tool because it is one contract
read at one place: it is folded into every declaring tool's schema, so editing
it changes what the model is asked for everywhere at once. Which tools must
declare one is `test_every_tool_that_acts_says_what_the_call_is_for`.
"""

from typing import Annotated

from pydantic import Field

Purpose = Annotated[
    str,
    Field(
        description=(
            "Short, plain-language phrase saying what this call is FOR. It is "
            "read aloud to a user who is listening, instead of the tool's "
            "generic line: 'Saving the parser fix'. Never the arguments "
            "themselves, and never the tool's name."
        )
    ),
]
