import datetime


def parse_cron_field(field: str, min_value: int, max_value: int):
    """Parse one cron field (e.g. `"*"`, `"1-5"`, `"1,3,5"`, `"*/10"`, `"1-10/2"`)
    into the set of integer values it matches, bounded by `min_value`/`max_value`.

    Raises `ValueError` on out-of-range values or non-positive steps — a
    silently never-matching field (e.g. minute `70`) is a schedule that never
    fires with no diagnostic.
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
                start, end = map(int, range_part.split("-"))
            else:
                start, end = int(range_part), max_value
            values.update(range(start, end + 1, step))
        elif "-" in part:
            start, end = map(int, part.split("-"))
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


def handle_special_cron_patterns(pattern: str, dt: datetime.datetime):
    """Whether `dt` matches a special `@`-prefixed pattern (`@yearly`, `@monthly`,
    `@weekly`, `@daily`/`@midnight`, `@hourly`, `@minutely`)."""
    if pattern == "@yearly" or pattern == "@annually":
        return dt.month == 1 and dt.day == 1 and dt.hour == 0 and dt.minute == 0
    elif pattern == "@monthly":
        return dt.day == 1 and dt.hour == 0 and dt.minute == 0
    elif pattern == "@weekly":
        return (
            dt.weekday() == 0 and dt.hour == 0 and dt.minute == 0
        )  # Monday at midnight
    elif pattern == "@daily" or pattern == "@midnight":
        return dt.hour == 0 and dt.minute == 0
    elif pattern == "@hourly":
        return dt.minute == 0
    elif pattern == "@minutely":
        return True
    return False


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
    # Max 7, not 6: cron accepts 7 for Sunday (the match below maps it to 0).
    days_of_week = parse_cron_field(day_of_week, 0, 7)
    # Convert Python's weekday (Mon=0..Sun=6) to cron's convention (Sun=0..Sat=6).
    # `isoweekday() % 7` maps Sun(7)->0, Mon(1)->1, ..., Sat(6)->6. Cron also
    # accepts 7 for Sunday, so treat it as equivalent to 0.
    cron_dow = dt.isoweekday() % 7
    day_of_month_match = dt.day in days
    weekday_match = cron_dow in days_of_week or (cron_dow == 0 and 7 in days_of_week)
    # Standard cron day semantics: when BOTH day-of-month and day-of-week are
    # restricted, the task runs if EITHER matches (OR). When at least one field
    # is the bare wildcard `*`, the fields are intersected (AND) — i.e. only the
    # restricted field constrains the schedule. Using AND here is correct because
    # a `*` field's membership test is always True, so it never narrows the match.
    if day == "*" or day_of_week == "*":
        day_match = day_of_month_match and weekday_match
    else:
        day_match = day_of_month_match or weekday_match
    return (
        dt.minute in minutes and dt.hour in hours and dt.month in months and day_match
    )
