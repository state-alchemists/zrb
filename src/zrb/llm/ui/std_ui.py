import asyncio
import subprocess
import sys
from typing import TYPE_CHECKING, Any, TextIO

from zrb.config.config import CFG
from zrb.util.cli.style import stylize_faint

if TYPE_CHECKING:
    from zrb.llm.tool_call.ui_protocol import ChoiceSpec

# Sentinel value for the synthetic "type my own answer" option.
_FREE_TEXT = "__zrb_free_text__"


def _option_text(opt: dict) -> str:
    label = opt.get("label", "")
    desc = opt.get("description", "")
    return f"{label} — {desc}" if desc else label


def resolve_choice_selection(spec: "ChoiceSpec", selection: Any) -> str:
    """Map a widget selection back to a label string (public, pure helper).

    `selection` is either a single option index, a list of indices
    (multi-select), or the `_FREE_TEXT` sentinel. Returns the joined label(s);
    free-text is handled by the caller before this point.
    """
    options = spec.get("options", [])
    indices = selection if isinstance(selection, list) else [selection]
    labels = [
        options[i].get("label", str(i))
        for i in indices
        if isinstance(i, int) and 0 <= i < len(options)
    ]
    return ", ".join(labels)


class StdUI:
    """Standard UI implementation of UIProtocol for terminal environments."""

    def __init__(self, assistant_name: str | None = None):
        raw = assistant_name if assistant_name else CFG.LLM_ASSISTANT_NAME
        self._assistant_name = raw[0].upper() + raw[1:] if raw else raw

    async def ask_user(self, prompt: str) -> str:
        """Prompt user via CLI input."""

        # lazy: heavy third-party
        from prompt_toolkit import PromptSession
        from prompt_toolkit.output import create_output

        # Always output to stderr to avoid polluting stdout
        output = create_output(stdout=sys.stderr)
        session = PromptSession(output=output)

        # Show a waiting indicator when no explicit prompt is provided
        # (the typical case for tool-confirmation requests).
        if not prompt:
            sys.stderr.write(
                f"\n👋 {self._assistant_name} is waiting for confirmation\n"
            )
            sys.stderr.flush()

        try:
            user_input = await session.prompt_async(prompt)
            return user_input.strip()
        except KeyboardInterrupt:
            # Let it propagate so the task runner can catch it or exit gracefully
            raise
        except EOFError:
            return ""

    async def ask_user_choice(self, spec: "ChoiceSpec") -> str:
        """Render an arrow-key-selectable multiple-choice dialog."""
        # lazy: heavy third-party
        from prompt_toolkit import PromptSession
        from prompt_toolkit.output import create_output
        from prompt_toolkit.shortcuts import checkboxlist_dialog, radiolist_dialog

        options = spec.get("options", [])
        if not options:
            return ""

        multi = bool(spec.get("multi_select"))
        idx, total = spec.get("index", 1), spec.get("total", 1)
        counter = f" ({idx}/{total})" if total > 1 else ""
        title = f"{spec.get('header', 'Question')}{counter}"
        values = [(i, _option_text(opt)) for i, opt in enumerate(options)]
        values.append((_FREE_TEXT, "✎ Type my own answer…"))

        dialog_factory = checkboxlist_dialog if multi else radiolist_dialog
        dialog = dialog_factory(
            title=title, text=spec.get("question", ""), values=values
        )
        # Route the transient full-screen dialog to stderr, matching ask_user.
        dialog.output = create_output(stdout=sys.stderr)
        selection = await dialog.run_async()

        if selection is None:
            # User cancelled (Esc / Cancel button).
            raise KeyboardInterrupt
        if selection == []:
            return "(no answer)"
        wants_free_text = selection == _FREE_TEXT or (multi and _FREE_TEXT in selection)
        if wants_free_text:
            session = PromptSession(output=create_output(stdout=sys.stderr))
            typed = (await session.prompt_async("Your answer: ")).strip()
            if multi:
                # Combine the checked options with the typed answer.
                checked = [i for i in selection if i != _FREE_TEXT]
                prefix = resolve_choice_selection(spec, checked)
                return ", ".join(part for part in (prefix, typed) if part)
            return typed
        return resolve_choice_selection(spec, selection)

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
        if kind not in ("text", "todo_progress"):
            content = stylize_faint(content)
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
        """Stream output immediately (same as append_to_output for StdUI).

        For StdUI, there's no buffering, so this is identical to append_to_output.
        """
        self.append_to_output(
            *values, sep=sep, end=end, file=file, flush=flush, kind=kind
        )

    async def run_interactive_command(
        self, cmd: str | list[str], shell: bool = False
    ) -> Any:
        """Run interactive commands using subprocess."""

        def _run():
            return subprocess.run(cmd, shell=shell)

        return await asyncio.to_thread(_run)
