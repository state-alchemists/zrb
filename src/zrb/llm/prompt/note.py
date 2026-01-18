import os
from typing import Callable

from zrb.context.any_context import AnyContext
from zrb.llm.note.manager import NoteManager
from zrb.util.markdown import make_markdown_section


def create_note_prompt(note_manager: NoteManager):
    def note_prompt(
        ctx: AnyContext,
        current_prompt: str,
        next_handler: Callable[[AnyContext, str], str],
    ) -> str:
        cwd = os.getcwd()
        notes = note_manager.read_all(cwd)

        if not notes:
            return next_handler(ctx, current_prompt)

        # Format notes
        note_lines = []

        # Sort keys for deterministic output
        sorted_keys = sorted(notes.keys())

        for key in sorted_keys:
            content = notes[key].strip()
            if not content:
                continue
            note_lines.append(f"**{key}**:\n{content}\n")

        if not note_lines:
            return next_handler(ctx, current_prompt)

        full_note_content = "\n".join(note_lines)
        note_block = make_markdown_section("Notes & Context", full_note_content)

        return next_handler(ctx, f"{current_prompt}\n\n{note_block}")

    return note_prompt
