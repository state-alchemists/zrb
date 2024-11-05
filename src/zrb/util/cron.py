import datetime


def parse_cron_field(field: str, min_value: int, max_value: int):
    """Parse a cron field with support for wildcards (*), ranges, lists, and steps."""
    values = set()
    if field == "*":
        return set(range(min_value, max_value + 1))
    elif field.startswith("*/"):
        # Handle step values like "*/5"
        step = int(field[2:])
        return set(range(min_value, max_value + 1, step))
    elif "-" in field or "," in field or "/" in field:
        # Handle ranges, lists, and steps
        parts = field.split(",")
        for part in parts:
            if "/" in part:
                range_part, step = part.split("/")
                step = int(step)
                if "-" in range_part:
                    start, end = map(int, range_part.split("-"))
                else:
                    start, end = int(range_part), max_value
                values.update(range(start, end + 1, step))
            elif "-" in part:
                start, end = map(int, part.split("-"))
                values.update(range(start, end + 1))
            else:
                values.add(int(part))
    else:
        # Handle individual values
        values.add(int(field))
    return values


def handle_special_cron_patterns(pattern: str, dt: datetime.datetime):
    """Handle special cron patterns like @yearly, @monthly, etc."""
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
    """Check if a datetime object matches a cron pattern, including special cases."""
    # Handle special cron patterns
    if cron_pattern.startswith("@"):
        return handle_special_cron_patterns(cron_pattern, dt)
    minute, hour, day, month, day_of_week = cron_pattern.split()
    # Parse each field with step, range, and wildcard support
    minutes = parse_cron_field(minute, 0, 59)
    hours = parse_cron_field(hour, 0, 23)
    days = parse_cron_field(day, 1, 31)
    months = parse_cron_field(month, 1, 12)
    days_of_week = parse_cron_field(day_of_week, 0, 6)
    # Match with standard cron behavior (day OR day_of_week must match)
    day_match = dt.day in days or dt.weekday() in days_of_week
    return (
        dt.minute in minutes and dt.hour in hours and dt.month in months and day_match
    )
