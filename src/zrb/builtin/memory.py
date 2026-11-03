"""`zrb memory migrate`: the upgrade path from the journal.

Memory is on by default and suppresses the journal, so an existing
`~/.zrb/llm-notes` would otherwise be unreachable after an upgrade: present on
disk, invisible to every session. This is the command the changelog names, and it
is read-only with respect to the journal — the old store stays where it is, so a
migration that surprises someone is one they can walk away from.
"""

from zrb.builtin.group import memory_group
from zrb.config.config import CFG
from zrb.context.any_context import AnyContext
from zrb.input.bool_input import BoolInput
from zrb.task.make_task import make_task
from zrb.util.string.conversion import to_boolean


@make_task(
    name="migrate-journal",
    description=(
        "🧠 Copy the journal into the memory store, leaving the journal untouched"
    ),
    input=BoolInput(
        name="dry_run",
        description="Count what would be written, and write nothing",
        prompt="Dry run?",
        default=False,
    ),
    group=memory_group,
    alias="migrate",
)
def migrate_journal(ctx: AnyContext) -> str:
    # lazy: the memory package loads pydantic_ai-dependent modules in the tools,
    # and this command must stay cheap to register.
    from zrb.llm.memory import paths
    from zrb.llm.memory.migrate import migrate

    dry_run = to_boolean(str(ctx.input.dry_run))
    counts = migrate(CFG.LLM_JOURNAL_DIR, dry_run)
    verb = "would write" if dry_run else "wrote"
    return (
        f"Memory store: {paths.memory_dir()}\n"
        f"{verb} {counts['facts']} facts, {counts['retired']} retired, "
        f"{counts['diary']} diary entries and {counts['log_lines']} log lines "
        f"from {CFG.LLM_JOURNAL_DIR}\n"
        "The journal was not modified; `ZRB_LLM_MEMORY_ENABLED=off` still "
        "selects it."
    )
