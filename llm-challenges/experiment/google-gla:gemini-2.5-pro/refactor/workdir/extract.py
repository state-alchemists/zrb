# etl_refactored/extract.py
import re
from typing import List, Optional

from .models import LogEntry

LOG_PATTERN = re.compile(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) (INFO|ERROR) (.*)")
USER_ACTION_PATTERN = re.compile(r"User (\d+) ")


def extract_logs(log_file: str) -> List[LogEntry]:
    """
    Extracts and parses logs from a file.

    Args:
        log_file: Path to the log file.

    Returns:
        A list of parsed log entries.
    """
    logs: List[LogEntry] = []
    try:
        with open(log_file, "r") as f:
            for line in f:
                match = LOG_PATTERN.match(line)
                if match:
                    date, log_type, message = match.groups()
                    parsed_log = _parse_log_entry(date, log_type, message)
                    if parsed_log:
                        logs.append(parsed_log)
    except FileNotFoundError:
        print(f"Log file not found: {log_file}")
    return logs


def _parse_log_entry(date: str, log_type: str, message: str) -> Optional[LogEntry]:
    """
    Parses a single log entry.

    Args:
        date: The timestamp of the log.
        log_type: The type of log (e.g., INFO, ERROR).
        message: The log message.

    Returns:
        A parsed log object or None if it's not a relevant log type.
    """
    if log_type == "ERROR":
        return LogEntry(date=date, message=message.strip(), log_type="ERROR")

    if log_type == "INFO":
        user_match = USER_ACTION_PATTERN.search(message)
        if user_match:
            user_id = user_match.group(1)
            return LogEntry(
                date=date,
                message=message.strip(),
                log_type="USER_ACTION",
                user_id=user_id,
            )
    return None
