"""
Journal prompt component.

Reads the journal index file and injects it into the system prompt.
Also includes reminders about maintaining AGENTS.md.
"""

import os
from typing import Callable

from zrb.config.config import CFG
from zrb.context.any_context import AnyContext

from zrb.util.markdown import make_markdown_section

def create_journal_prompt():
    def journal_prompt(
        ctx: AnyContext,
        current_prompt: str,
        next_handler: Callable[[AnyContext, str], str],
    ) -> str:
        # Get the journal index file path
        effective_journal_dir = os.path.abspath(os.path.expanduser(CFG.LLM_JOURNAL_DIR))
        if not os.path.isdir(effective_journal_dir):
            os.makedirs(effective_journal_dir, exist_ok=True)
        index_path = os.path.join(effective_journal_dir, CFG.LLM_JOURNAL_INDEX_FILE)
        if not os.path.isfile(index_path):
            with open(index_path, "w") as f:
                f.write("")
        # Read the index file if it exists
        journal_content = ""
        with open(index_path, "r", encoding="utf-8") as f:
            journal_content = f.read().strip()
        # Create the prompt sections
        sections = []
        # Add journal content if available
        if journal_content:
            journal_section = make_markdown_section("Journal & Notes", journal_content)
            sections.append(journal_section)
        # Always add the journal configuration information
        journal_info = (
            "**Journal System Configuration:**\n"
            f"- **Journal Directory:** `{CFG.LLM_JOURNAL_DIR}`\n"
            f"- **Index File:** `{CFG.LLM_JOURNAL_INDEX_FILE}`\n\n"
            "**Documentation Guidelines:**\n"
            "- Technical information about project architecture, conventions, and patterns should be maintained in `AGENTS.md`\n"
            "- User preferences, non-technical context, and session notes can be added to the journal directory\n"
            "- At the end of significant interactions, consider updating relevant documentation"
        )
        info_section = make_markdown_section("Journal System", journal_info)
        sections.append(info_section)
        # Combine all sections
        if sections:
            combined_sections = "\n\n".join(sections)
            return next_handler(ctx, f"{current_prompt}\n\n{combined_sections}")
        # If no sections were added, just pass through
        return next_handler(ctx, current_prompt)
    
    return journal_prompt