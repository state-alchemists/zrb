"""Log parsing module with robust regex-based parsing.

Handles various log formats and is resilient to extra whitespace.
"""

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal, Optional


@dataclass(frozen=True)
class LogEntry:
    """Represents a parsed log entry."""
    timestamp: datetime
    level: Literal["ERROR", "INFO", "WARN", "DEBUG"]
    message: str
    user_id: Optional[str] = None


# Log line format: YYYY-MM-DD HH:MM:SS LEVEL [details...]
# Uses flexible whitespace handling
LOG_PATTERN = re.compile(
    r"^\s*(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\s+"  # Timestamp
    r"([A-Z]+)\s+"  # Log level
    r"(.*)$"  # Rest of message
)

# User extraction pattern: "User <id>" anywhere in the message
USER_PATTERN = re.compile(r"User\s+(\d+)")


def parse_log_line(line: str) -> Optional[LogEntry]:
    """Parse a single log line into a LogEntry.
    
    Args:
        line: A single line from the log file.
        
    Returns:
        LogEntry if the line matches expected format, None otherwise.
    """
    match = LOG_PATTERN.match(line)
    if not match:
        return None
    
    timestamp_str, level, message = match.groups()
    
    try:
        timestamp = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None
    
    # Extract user ID if present (resilient to whitespace variations)
    user_match = USER_PATTERN.search(message)
    user_id = user_match.group(1) if user_match else None
    
    return LogEntry(
        timestamp=timestamp,
        level=level,
        message=message.strip(),
        user_id=user_id
    )


def parse_log_file(filepath: str | Path) -> list[LogEntry]:
    """Parse an entire log file.
    
    Args:
        filepath: Path to the log file.
        
    Returns:
        List of parsed LogEntry objects.
    """
    entries: list[LogEntry] = []
    
    path = Path(filepath)
    if not path.exists():
        return entries
    
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:  # Skip empty lines
                entry = parse_log_line(line)
                if entry:
                    entries.append(entry)
    
    return entries
