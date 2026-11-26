import datetime

from zrb.builtin.group import cron_group
from zrb.context.any_context import AnyContext
from zrb.input.int_input import IntInput
from zrb.input.str_input import StrInput
from zrb.task.make_task import make_task
from zrb.util.cron import match_cron, validate_cron_expression

# Cap the forward scan so an impossible pattern (e.g. "0 0 30 2 *") terminates
# instead of looping forever.
_MAX_SCAN_MINUTES = 366 * 24 * 60 * 5


def _validate_cron_expression(ctx: AnyContext, expression: str) -> None:
    """Report a malformed cron expression to the user, then raise."""
    try:
        validate_cron_expression(expression)
    except ValueError as e:
        ctx.print_err(f"❌ {e}")
        raise


@make_task(
    name="parse-cron",
    description="📅 Validate a cron expression and show its next run times",
    input=[
        StrInput(
            name="expression",
            description="Cron expression (e.g. '*/5 * * * *' or '@daily')",
            prompt="Cron expression",
        ),
        IntInput(
            name="count",
            description="How many upcoming run times to show",
            prompt="Number of upcoming runs",
            default=5,
            always_prompt=False,
        ),
    ],
    retries=0,
    group=cron_group,
    alias="parse",
)
def parse_cron(ctx: AnyContext) -> str:
    expression = ctx.input.expression.strip()
    _validate_cron_expression(ctx, expression)

    now = datetime.datetime.now().replace(second=0, microsecond=0)
    candidate = now + datetime.timedelta(minutes=1)
    runs: list[str] = []
    scanned = 0
    while len(runs) < ctx.input.count and scanned < _MAX_SCAN_MINUTES:
        if match_cron(expression, candidate):
            runs.append(candidate.isoformat())
        candidate += datetime.timedelta(minutes=1)
        scanned += 1

    ctx.print(f"✅ Valid cron expression: {expression}")
    ctx.print("Next runs:")
    for run in runs:
        ctx.print(f"  {run}")
    if len(runs) < ctx.input.count:
        ctx.print(
            f"  (only {len(runs)} run(s) found within the next "
            f"{_MAX_SCAN_MINUTES // (24 * 60)} days)"
        )
    return "\n".join(runs)
