"""The UI's capability contracts — what a layer beneath `ui/` may name.

A role of `AnyUI` lives here when something lower has to type against it:
`tool_call`, `approval`, `dictation` and `custom_command` write the user's
output and read the input side, and `tool/ask.py` builds a choice question.
None of them build a UI, so none of them need the object — only the capability.

`AnyUI` itself stays in `zrb.llm.ui` beside the UIs that answer it. A role that
is only ever reached through an accessor (`display`, `session`, `tools`) stays
there too: nothing below names it, so moving it would be distance without a
reason.

This package deliberately imports nothing but its own modules. Importing
`zrb.llm.contracts.ui.any_ui_input` must not load `zrb.llm.ui`: if the
capability dragged the UI with it, the upward edge would only have moved to
import time. `test/llm/contracts/ui/test_capability_stays_low.py` holds that.
"""
