import datetime
from collections.abc import Callable


def parse_cron_field(field: str, min_value: int, max_value: int):
    """Parse one cron field (e.g. `"*"`, `"1-5"`, `"1,3,5"`, `"*/10"`, `"1-10/2"`)
    into the set of integer values it matches, bounded by `min_value`/`max_value`.

    Raises `ValueError` on out-of-range values, reversed ranges, or non-positive
    steps.
    """
    values: set[int] = set()
    # Parse per list item so a wildcard step inside a list ("1,*/5") works.
    for part in field.split(","):
        if part == "*":
            values.update(range(min_value, max_value + 1))
        elif "/" in part:
            range_part, step_str = part.split("/")
            step = int(step_str)
            if step <= 0:
                raise ValueError(f"Invalid step {step} in cron field '{field}'")
            if range_part == "*":
                start, end = min_value, max_value
            elif "-" in range_part:
                start, end = _parse_cron_range(range_part, field, min_value, max_value)
            else:
                start, end = int(range_part), max_value
                # Without this, "70/5" built an empty range and silently
                # matched nothing instead of reporting the invalid bound.
                _check_cron_value(start, field, min_value, max_value)
            values.update(range(start, end + 1, step))
        elif "-" in part:
            start, end = _parse_cron_range(part, field, min_value, max_value)
            values.update(range(start, end + 1))
        else:
            values.add(int(part))
    out_of_range = sorted(v for v in values if v < min_value or v > max_value)
    if out_of_range:
        raise ValueError(
            f"Cron field '{field}' has out-of-range values {out_of_range} "
            f"(allowed: {min_value}-{max_value})"
        )
    return values


def _parse_cron_range(
    part: str, field: str, min_value: int, max_value: int
) -> tuple[int, int]:
    """`start-end` bounds checked; a reversed range is an error, not an empty set."""
    start, end = map(int, part.split("-"))
    _check_cron_value(start, field, min_value, max_value)
    _check_cron_value(end, field, min_value, max_value)
    if start > end:
        raise ValueError(
            f"Cron field '{field}' has a reversed range '{part}' "
            f"(start must not be greater than end)"
        )
    return start, end


def _check_cron_value(value: int, field: str, min_value: int, max_value: int) -> None:
    if value < min_value or value > max_value:
        raise ValueError(
            f"Cron field '{field}' has out-of-range value {value} "
            f"(allowed: {min_value}-{max_value})"
        )


def _is_yearly(dt: datetime.datetime) -> bool:
    return (dt.month, dt.day, dt.hour, dt.minute) == (1, 1, 0, 0)


def _is_midnight(dt: datetime.datetime) -> bool:
    return (dt.hour, dt.minute) == (0, 0)


# The `@`-prefixed shorthands, each mapped to what it matches.
_SPECIAL_CRON_MATCHERS: dict[str, Callable[[datetime.datetime], bool]] = {
    "@yearly": _is_yearly,
    "@annually": _is_yearly,
    "@monthly": lambda dt: (dt.day, dt.hour, dt.minute) == (1, 0, 0),
    # Sunday at midnight, as Vixie cron and cronie define it. Python's
    # `weekday()` puts Sunday last.
    "@weekly": lambda dt: (dt.weekday(), dt.hour, dt.minute) == (6, 0, 0),
    "@daily": _is_midnight,
    "@midnight": _is_midnight,
    "@hourly": lambda dt: dt.minute == 0,
    "@minutely": lambda dt: True,
}


def handle_special_cron_patterns(pattern: str, dt: datetime.datetime):
    """Whether `dt` matches a special `@`-prefixed pattern (`@yearly`, `@monthly`,
    `@weekly`, `@daily`/`@midnight`, `@hourly`, `@minutely`)."""
    matcher = _SPECIAL_CRON_MATCHERS.get(pattern)
    return matcher(dt) if matcher is not None else False


def validate_cron_expression(expression: str) -> None:
    """Raise `ValueError` naming why `expression` is not a usable cron pattern.

    `match_cron` only refuses what it cannot parse, so an unknown `@` shortcut
    matches nothing at all; anything scheduled on one would wait forever without
    saying so. Call this wherever a pattern is accepted.
    """
    if expression.startswith("@"):
        if expression not in _SPECIAL_CRON_MATCHERS:
            raise ValueError(
                f"Unknown cron shortcut '{expression}'. "
                f"Supported shortcuts: {', '.join(sorted(_SPECIAL_CRON_MATCHERS))}."
            )
        return
    fields = expression.split()
    if len(fields) != 5:
        raise ValueError(
            f"Invalid cron expression '{expression}': expected 5 space-separated "
            f"fields (minute hour day-of-month month day-of-week) but got "
            f"{len(fields)}. Example: '*/5 * * * *', or a shortcut like '@daily'."
        )
    try:
        # match_cron parses every field; a non-numeric/garbage field raises here.
        match_cron(expression, datetime.datetime(2000, 1, 1))
    except ValueError as e:
        raise ValueError(
            f"Invalid cron expression '{expression}': could not parse a field "
            f"({e}). Each field must be a number, range (1-5), list (1,3,5), "
            f"step (*/5), or wildcard (*)."
        ) from None


def match_cron(cron_pattern: str, dt: datetime.datetime):
    """Whether `dt` matches `cron_pattern` — standard 5-field cron
    (`minute hour day month day_of_week`) or an `@`-prefixed special pattern."""
    if cron_pattern.startswith("@"):
        return handle_special_cron_patterns(cron_pattern, dt)
    minute, hour, day, month, day_of_week = cron_pattern.split()
    minutes = parse_cron_field(minute, 0, 59)
    hours = parse_cron_field(hour, 0, 23)
    days = parse_cron_field(day, 1, 31)
    months = parse_cron_field(month, 1, 12)
    # Max 7, not 6: cron accepts 7 for Sunday, treated as equivalent to 0.
    days_of_week = parse_cron_field(day_of_week, 0, 7)
    # Cron's day of week is Sun=0..Sat=6; `isoweekday() % 7` maps Sun(7) to 0.
    cron_dow = dt.isoweekday() % 7
    day_of_month_match = dt.day in days
    weekday_match = cron_dow in days_of_week or (cron_dow == 0 and 7 in days_of_week)
    # Cron semantics: when both day-of-month and day-of-week are restricted,
    # either may match (OR); otherwise AND, since a `*` field always matches.
    # A star is the field's *first* character, not the whole field: cronie reads
    # `*/2` as a star flag too, so `0 0 */2 * 1` runs on odd days that are also
    # Mondays, never on every Monday.
    if day.startswith("*") or day_of_week.startswith("*"):
        day_match = day_of_month_match and weekday_match
    else:
        day_match = day_of_month_match or weekday_match
    return (
        dt.minute in minutes and dt.hour in hours and dt.month in months and day_match
    )
