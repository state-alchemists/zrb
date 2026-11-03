"""`zrb memory migrate`: read a notes directory into the memory store.

An existing `~/.zrb/llm-notes` is already read once, on first use, when the
store lives inside it (``paths.should_convert``). This command is the explicit
way to do that — a dry run that counts first, or a store pointed somewhere else
that should still be filled from the notes.

It is read-only with respect to the notes: the old files stay where they are, so
a migration that surprises someone is one they can walk away from.
"""

from zrb.builtin.group import memory_group
from zrb.config.config import CFG
from zrb.context.any_context import AnyContext
from zrb.input.bool_input import BoolInput
from zrb.task.make_task import make_task
from zrb.util.string.conversion import to_boolean


@make_task(
    name="migrate",
    description=(
        "🧠 Read the notes directory into the memory store, leaving the notes "
        "untouched"
    ),
    input=BoolInput(
        name="dry_run",
        description="Count what would be written, and write nothing",
        prompt="Dry run?",
        default=False,
    ),
    group=memory_group,
)
def migrate_notes(ctx: AnyContext) -> str:
    # lazy: the memory package loads pydantic_ai-dependent modules in the tools,
    # and this command must stay cheap to register.
    from zrb.llm.memory import paths
    from zrb.llm.memory.migrate import migrate

    dry_run = to_boolean(str(ctx.input.dry_run))
    counts = migrate(CFG.LLM_NOTES_DIR, dry_run)
    verb = "would write" if dry_run else "wrote"
    unpinned = counts.get("unpinned", 0)
    converted = counts.get("converted", 0)
    notes = ""
    if unpinned:
        notes += (
            f"\nUnpinned {unpinned} claim(s) that did not fit the core: they stay "
            "searchable and out of every first turn."
        )
    if converted:
        notes += (
            f"\nTurned {converted} open loop(s) into facts so the core fits: their "
            "claims are unchanged and still searchable."
        )
    return (
        f"Memory store: {paths.memory_dir()}\n"
        f"{verb} {counts['facts']} facts, {counts['retired']} retired, "
        f"{counts['diary']} diary entries and {counts['log_lines']} log lines "
        f"from {CFG.LLM_NOTES_DIR}{notes}\n"
        "The notes were not modified: they stay beside the store as the record "
        "it was read from."
    )
