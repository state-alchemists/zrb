import datetime

from zrb.builtin.group import time_group
from zrb.context.any_context import AnyContext
from zrb.input.option_input import OptionInput
from zrb.input.str_input import StrInput
from zrb.task.make_task import make_task


def _tzinfo(name: str) -> datetime.timezone | None:
    # "local" -> None lets datetime use the system local timezone.
    return datetime.timezone.utc if name == "utc" else None


@make_task(
    name="now",
    description="🕒 Show the current time as epoch and ISO 8601",
    input=OptionInput(
        name="timezone",
        description="Timezone for the ISO output",
        prompt="Timezone",
        default="utc",
        options=["utc", "local"],
        always_prompt=False,
    ),
    group=time_group,
    alias="now",
)
def now(ctx: AnyContext) -> str:

    moment = datetime.datetime.now(tz=_tzinfo(ctx.input.timezone))
    epoch = int(moment.timestamp())
    ctx.print(f"Epoch:   {epoch}")
    ctx.print(f"ISO8601: {moment.isoformat()}")
    return str(epoch)


@make_task(
    name="epoch-to-iso",
    description="🕒 Convert a Unix epoch timestamp to ISO 8601",
    input=[
        StrInput(
            name="epoch",
            description="Unix timestamp (seconds; fractional allowed)",
            prompt="Epoch timestamp",
        ),
        OptionInput(
            name="timezone",
            description="Timezone for the ISO output",
            prompt="Timezone",
            default="utc",
            options=["utc", "local"],
            always_prompt=False,
        ),
    ],
    retries=0,
    group=time_group,
    alias="to-iso",
)
def epoch_to_iso(ctx: AnyContext) -> str:

    try:
        epoch = float(ctx.input.epoch)
    except ValueError:
        message = (
            f"Invalid epoch '{ctx.input.epoch}': expected a number of seconds "
            f"since 1970-01-01 (e.g. 1750000000)."
        )
        ctx.print_err(f"❌ {message}")
        raise ValueError(message) from None
    moment = datetime.datetime.fromtimestamp(epoch, tz=_tzinfo(ctx.input.timezone))
    result = moment.isoformat()
    ctx.print(result)
    return result


@make_task(
    name="iso-to-epoch",
    description="🕒 Convert an ISO 8601 datetime to a Unix epoch timestamp",
    input=StrInput(
        name="datetime",
        description="ISO 8601 datetime (e.g. 2026-06-14T10:00:00Z)",
        prompt="ISO 8601 datetime",
    ),
    retries=0,
    group=time_group,
    alias="to-epoch",
)
def iso_to_epoch(ctx: AnyContext) -> str:

    try:
        moment = datetime.datetime.fromisoformat(ctx.input.datetime)
    except ValueError:
        message = (
            f"Invalid ISO 8601 datetime '{ctx.input.datetime}': expected a value "
            f"like '2026-06-14T10:00:00Z', '2026-06-14T10:00:00+07:00', or "
            f"'2026-06-14'."
        )
        ctx.print_err(f"❌ {message}")
        raise ValueError(message) from None
    # A naive datetime (no offset) is interpreted as UTC for a stable result.
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=datetime.timezone.utc)
    result = str(int(moment.timestamp()))
    ctx.print(result)
    return result
