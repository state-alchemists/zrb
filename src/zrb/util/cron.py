import datetime


def parse_cron_field(field: str, min_value: int, max_value: int):
    """
    Parse a cron field string into a set of integer values.

    Supports wildcards (*), ranges (e.g., 1-5), lists (e.g., 1,3,5),
    and step values (e.g., */5, 1-10/2).

    Args:
        field (str): The cron field string (e.g., "*", "1-5", "*/10").
        min_value (int): The minimum allowed value for the field.
        max_value (int): The maximum allowed value for the field.

    Returns:
        set[int]: A set of integer values represented by the cron field.
    """
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
    """
    Check if a datetime object matches a special cron pattern.

    Args:
        pattern (str): The special cron pattern (e.g., "@yearly", "@monthly").
        dt (datetime.datetime): The datetime object to check.

    Returns:
        bool: True if the datetime matches the pattern, False otherwise.
    """
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
    """
    Check if a datetime object matches a cron pattern.

    Supports standard cron format (minute hour day month day_of_week)
    and special patterns (e.g., "@yearly", "@monthly").

    Args:
        cron_pattern (str): The cron pattern string.
        dt (datetime.datetime): The datetime object to check.

    Returns:
        bool: True if the datetime matches the cron pattern, False otherwise.
    """
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
