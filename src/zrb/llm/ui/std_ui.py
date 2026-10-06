import asyncio
import subprocess
import sys
from typing import TYPE_CHECKING, Any, TextIO

from zrb.config.config import CFG
from zrb.llm.tool_call.choice_spec_format import get_option_label
from zrb.llm.ui.any_ui import AnyUI
from zrb.llm.ui.state_defaults import UIStateDefaultsMixin
from zrb.util.cli.style import stylize_muted

if TYPE_CHECKING:
    from zrb.llm.ui.any_ui import ChoiceOption, ChoiceSpec

# Sentinel value for the synthetic "type my own answer" option.
FREE_TEXT = "__zrb_free_text__"


def option_text(opt: "ChoiceOption", index: int) -> str:
    """*opt*'s row text, labelled by its *index* in the option list."""
    label = get_option_label(opt, index)
    desc = opt.get("description", "")
    return f"{label} — {desc}" if desc else label


def resolve_choice_selection(spec: "ChoiceSpec", selection: Any) -> str:
    """Map a widget selection (an index or a list of indices) to joined labels."""
    options = spec.get("options", [])
    indices = selection if isinstance(selection, list) else [selection]
    labels = [
        get_option_label(options[i], i)
        for i in indices
        if isinstance(i, int) and 0 <= i < len(options)
    ]
    return ", ".join(labels)


class StdUI(UIStateDefaultsMixin, AnyUI):
    """Standard UI implementation of AnyUI for terminal environments."""

    def __init__(self, assistant_name: str | None = None):
        raw = assistant_name if assistant_name else CFG.LLM_ASSISTANT_NAME
        self._assistant_name = raw[0].upper() + raw[1:] if raw else raw

    async def ask_user(
        self,
        prompt: str,
        output_to_parent: str = "",
        agent_id: str | None = None,
    ) -> str:
        """Prompt user via CLI input."""
        # lazy: heavy third-party
        from prompt_toolkit import PromptSession
        from prompt_toolkit.output import create_output

        # stderr, so stdout carries only the result.
        output = create_output(stdout=sys.stderr)
        session = PromptSession(output=output)

        # No prompt is the tool-confirmation case.
        if not prompt:
            sys.stderr.write(
                f"\n👋 {self._assistant_name} is waiting for confirmation\n"
            )
            sys.stderr.flush()

        try:
            user_input = await session.prompt_async(prompt)
            return user_input.strip()
        except EOFError:
            return ""

    async def ask_user_choice(
        self, spec: "ChoiceSpec", agent_id: str | None = None
    ) -> str:
        """Render an arrow-key-selectable multiple-choice dialog."""
        # lazy: heavy third-party
        from prompt_toolkit.output import create_output
        from prompt_toolkit.shortcuts import checkboxlist_dialog, radiolist_dialog

        options = spec.get("options", [])
        if not options:
            return ""
        multi = bool(spec.get("multi_select"))
        dialog_factory = checkboxlist_dialog if multi else radiolist_dialog
        dialog = dialog_factory(
            title=_choice_title(spec),
            text=spec.get("question", ""),
            values=_choice_values(options),
        )
        # Route the transient full-screen dialog to stderr, matching ask_user.
        dialog.output = create_output(stdout=sys.stderr)
        selection = await dialog.run_async()

        if selection is None:
            # User cancelled (Esc / Cancel button).
            raise KeyboardInterrupt
        if selection == []:
            return "(no answer)"
        if _wants_free_text(selection):
            return await self._ask_free_text(spec, selection, multi)
        return resolve_choice_selection(spec, selection)

    async def _ask_free_text(
        self, spec: "ChoiceSpec", selection: Any, multi: bool
    ) -> str:
        """Prompt for a typed answer, folding in any options also checked."""
        # lazy: heavy third-party
        from prompt_toolkit import PromptSession
        from prompt_toolkit.output import create_output

        session = PromptSession(output=create_output(stdout=sys.stderr))
        typed = (await session.prompt_async("Your answer: ")).strip()
        if multi and isinstance(selection, list):
            checked = [i for i in selection if i != FREE_TEXT]
            prefix = resolve_choice_selection(spec, checked)
            return ", ".join(part for part in (prefix, typed) if part)
        return typed

    def append_to_output(
        self,
        *values: object,
        sep: str = " ",
        end: str = "\n",
        file: TextIO | None = None,
        flush: bool = False,
        kind: str = "text",
    ):
        """Print output to stderr."""
        content = sep.join(str(v) for v in values) + end
        # The usage line is the turn's last and is never newline-terminated
        # upstream; without this the stdout result lands on the same line.
        if kind == "usage" and not content.endswith("\n"):
            content += "\n"
        if kind not in ("text", "todo_progress"):
            content = stylize_muted(content)
        sys.stderr.write(content)
        if flush:
            sys.stderr.flush()

    def stream_to_parent(
        self,
        *values: object,
        sep: str = " ",
        end: str = "\n",
        file: TextIO | None = None,
        flush: bool = False,
        kind: str = "text",
    ):
        """Identical to `append_to_output`: StdUI does not buffer."""
        self.append_to_output(
            *values, sep=sep, end=end, file=file, flush=flush, kind=kind
        )

    async def run_interactive_command(
        self, cmd: str | list[str], shell: bool = False
    ) -> Any:
        """Run interactive commands using subprocess."""
        return await asyncio.to_thread(subprocess.run, cmd, shell=shell)

    async def run_async(self) -> Any:
        """No-op: StdUI is a non-interactive adapter with no loop of its own."""
        return None


def _choice_title(spec: "ChoiceSpec") -> str:
    """The dialog title, carrying an `(n/total)` counter for a multi-question run."""
    index, total = spec.get("index", 1), spec.get("total", 1)
    counter = f" ({index}/{total})" if total > 1 else ""
    return f"{spec.get('header', 'Question')}{counter}"


def _choice_values(options: list) -> list[tuple[int | str, str]]:
    """The selectable rows, with the free-text escape hatch appended last."""
    values: list[tuple[int | str, str]] = [
        (i, option_text(opt, i)) for i, opt in enumerate(options)
    ]
    values.append((FREE_TEXT, "✎ Type my own answer…"))
    return values


def _wants_free_text(selection: Any) -> bool:
    """Whether the user picked the free-text row, in either dialog shape."""
    return selection == FREE_TEXT or (
        isinstance(selection, list) and FREE_TEXT in selection
    )
