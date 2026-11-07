"""The interactive line the live context renders, and what it must not say.

The non-interactive branch is the one where the interactive-only tools are
absent, so naming them there is waste: the model cannot call what it cannot see,
and a guard that lists tools reads as a contract they do not have.
"""

from zrb.context.context import Context
from zrb.context.shared_context import SharedContext
from zrb.llm.prompt.live_context.context import render_live_context


def _ctx(interactive: bool) -> Context:
    "A real task context carrying the interactivity flag the render reads."
    shared_ctx = SharedContext(input={"interactive": interactive, "session": "t"})
    return Context(shared_ctx, "test", 0, "")


def _live_context(model: str, *, interactive: bool = True) -> str:
    "Render a live-context block as *model*'s preset would receive it."
    return render_live_context(_ctx(interactive), model, inject_memory=True)


def test_the_non_interactive_line_forbids_no_tool_by_name():
    "Those tools are unregistered in exactly this branch, so naming them is waste."
    text = _live_context("anthropic:claude-opus-4-8", interactive=False)

    assert "Interactive: no" in text

    guard = next(
        line for line in text.splitlines() if line.startswith("- Interactive:")
    )
    for tool in ("AskUserQuestion", "EnterPlanMode", "ExitPlanMode"):
        assert tool not in guard
