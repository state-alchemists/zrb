"""
Server log processing pipeline.

Extracts events from server logs, aggregates metrics, and generates an HTML report.

Usage:
    python pipeline_refactored.py

Environment variables:
    LOG_FILE_PATH      Path to the server log file (default: server.log)
    METRICS_DB_PATH    Path to the SQLite database (default: metrics.db)
    DB_HOST            Database host (default: localhost)
    DB_PORT            Database port (default: 5432)
    DB_USER            Database user (default: admin)
    DB_PASS            Database password (default: password123)
"""

from __future__ import annotations

import datetime
import os
import re
import sqlite3
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, TypedDict


# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

class LogLevel(Enum):
    """Supported log severity levels."""
    INFO = "INFO"
    ERROR = "ERROR"
    WARN = "WARN"


@dataclass(frozen=True)
class LogEntry:
    """Represents a parsed log entry."""
    timestamp: str
    level: LogLevel
    raw: str


@dataclass(frozen=True)
class ErrorEntry(LogEntry):
    """Log entry representing an error."""
    message: str


@dataclass(frozen=True)
class UserActionEntry(LogEntry):
    """Log entry representing a user action."""
    user_id: str
    action: str


@dataclass(frozen=True)
class ApiCallEntry(LogEntry):
    """Log entry representing an API call."""
    endpoint: str
    duration_ms: int


@dataclass(frozen=True)
class WarningEntry(LogEntry):
    """Log entry representing a warning."""
    message: str


class ParsedEntries(TypedDict):
    errors: List[ErrorEntry]
    user_actions: List[UserActionEntry]
    api_calls: List[ApiCallEntry]
    warnings: List[WarningEntry]


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

def get_config() -> Dict[str, str]:
    """Load configuration from environment variables with sensible defaults."""
    return {
        "log_file": os.environ.get("LOG_FILE_PATH", "server.log"),
        "db_path": os.environ.get("METRICS_DB_PATH", "metrics.db"),
        "db_host": os.environ.get("DB_HOST", "localhost"),
        "db_port": os.environ.get("DB_PORT", "5432"),
        "db_user": os.environ.get("DB_USER", "admin"),
        "db_pass": os.environ.get("DB_PASS", "password123"),
    }


# ---------------------------------------------------------------------------
# EXTRACT — Log parsing
# ---------------------------------------------------------------------------

# Compiled patterns for performance (module-level, compiled once)
_RE_LOG_LINE = re.compile(
    r"^(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) "
    r"(?P<level>INFO|ERROR|WARN)\s+(?P<body>.*)$"
)

_RE_USER_ACTION = re.compile(
    r"^User (?P<user_id>\d+) (?P<action>.*)$"
)

_RE_API_CALL = re.compile(
    r"^API (?P<endpoint>\S+) took (?P<duration>\d+)ms$"
)


def _parse_log_line(line: str) -> Optional[LogEntry]:
    """
    Parse a single log line into a structured LogEntry.

    Returns None if the line does not match the expected format.

    Args:
        line: A single line from the server log.

    Returns:
        A LogEntry subclass instance, or None if parsing fails.
    """
    line = line.strip()
    if not line:
        return None

    match = _RE_LOG_LINE.match(line)
    if not match:
        return None

    timestamp = match.group("timestamp")
    level_str = match.group("level")
    body = match.group("body")

    try:
        level = LogLevel(level_str)
    except ValueError:
        return None

    # ERROR: rest of line is the error message
    if level is LogLevel.ERROR:
        return ErrorEntry(timestamp=timestamp, level=level, raw=line, message=body.strip())

    # WARN: rest of line is the warning message
    if level is LogLevel.WARN:
        return WarningEntry(timestamp=timestamp, level=level, raw=line, message=body.strip())

    # INFO — distinguish user actions from API calls
    if level is LogLevel.INFO:
        user_match = _RE_USER_ACTION.match(body)
        if user_match:
            return UserActionEntry(
                timestamp=timestamp,
                level=level,
                raw=line,
                user_id=user_match.group("user_id"),
                action=user_match.group("action").strip(),
            )

        api_match = _RE_API_CALL.match(body)
        if api_match:
            return ApiCallEntry(
                timestamp=timestamp,
                level=level,
                raw=line,
                endpoint=api_match.group("endpoint"),
                duration_ms=int(api_match.group("duration")),
            )

    return None


def extract_log_entries(log_path: str) -> ParsedEntries:
    """
    Read and parse all log entries from a file.

    Args:
        log_path: Path to the server log file.

    Returns:
        A dict with keys: errors, user_actions, api_calls, warnings.
        Each value is a list of typed entries.
    """
    entries: ParsedEntries = {
        "errors": [],
        "user_actions": [],
        "api_calls": [],
        "warnings": [],
    }

    if not os.path.exists(log_path):
        print(f"Warning: log file not found at {log_path}")
        return entries

    with open(log_path, "r") as fh:
        for line in fh:
            entry = _parse_log_line(line)
            if entry is None:
                continue

            if isinstance(entry, ErrorEntry):
                entries["errors"].append(entry)
            elif isinstance(entry, UserActionEntry):
                entries["user_actions"].append(entry)
            elif isinstance(entry, ApiCallEntry):
                entries["api_calls"].append(entry)
            elif isinstance(entry, WarningEntry):
                entries["warnings"].append(entry)

    return entries


# ---------------------------------------------------------------------------
# TRANSFORM — Aggregation
# ---------------------------------------------------------------------------

def aggregate_errors(errors: List[ErrorEntry]) -> Dict[str, int]:
    """
    Count occurrences of each distinct error message.

    Args:
        errors: List of parsed error entries.

    Returns:
        Dict mapping error message to occurrence count.
    """
    counts: Dict[str, int] = {}
    for err in errors:
        counts[err.message] = counts.get(err.message, 0) + 1
    return counts


def aggregate_api_latency(api_calls: List[ApiCallEntry]) -> Dict[str, float]:
    """
    Compute average latency per endpoint.

    Args:
        api_calls: List of parsed API call entries.

    Returns:
        Dict mapping endpoint to average duration in ms.
    """
    latency_by_endpoint: Dict[str, List[int]] = {}
    for call in api_calls:
        latency_by_endpoint.setdefault(call.endpoint, []).append(call.duration_ms)

    return {
        endpoint: sum(times) / len(times)
        for endpoint, times in latency_by_endpoint.items()
    }


def track_active_sessions(user_actions: List[UserActionEntry]) -> int:
    """
    Determine the number of currently active user sessions.

    A user is considered active if they have logged in but not yet logged out.

    Args:
        user_actions: List of parsed user action entries.

    Returns:
        Count of currently active sessions.
    """
    active_users: Dict[str, str] = {}  # user_id -> login_timestamp

    for action in user_actions:
        uid = action.user_id
        if "logged in" in action.action:
            active_users[uid] = action.timestamp
        elif "logged out" in action.action and uid in active_users:
            del active_users[uid]

    return len(active_users)


# ---------------------------------------------------------------------------
# LOAD — Database and report generation
# ---------------------------------------------------------------------------

def init_database(conn: sqlite3.Connection) -> None:
    """
    Create the required tables if they do not exist.

    Args:
        conn: Active SQLite database connection.
    """
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS errors (
            dt TEXT,
            message TEXT,
            count INTEGER
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS api_metrics (
            dt TEXT,
            endpoint TEXT,
            avg_ms REAL
        )
        """
    )


def persist_error_counts(conn: sqlite3.Connection, error_counts: Dict[str, int]) -> None:
    """
    Insert aggregated error counts into the database using parameterized queries.

    Args:
        conn: Active SQLite database connection.
        error_counts: Map of error message to occurrence count.
    """
    if not error_counts:
        return

    cur = conn.cursor()
    timestamp = datetime.datetime.now().isoformat()
    cur.executemany(
        "INSERT INTO errors (dt, message, count) VALUES (?, ?, ?)",
        [(timestamp, msg, cnt) for msg, cnt in error_counts.items()],
    )


def persist_api_metrics(conn: sqlite3.Connection, endpoint_avg: Dict[str, float]) -> None:
    """
    Insert API latency averages into the database using parameterized queries.

    Args:
        conn: Active SQLite database connection.
        endpoint_avg: Map of endpoint to average duration in ms.
    """
    if not endpoint_avg:
        return

    cur = conn.cursor()
    timestamp = datetime.datetime.now().isoformat()
    cur.executemany(
        "INSERT INTO api_metrics (dt, endpoint, avg_ms) VALUES (?, ?, ?)",
        [(timestamp, ep, avg) for ep, avg in endpoint_avg.items()],
    )


def generate_html_report(
    error_counts: Dict[str, int],
    api_latency: Dict[str, float],
    active_sessions: int,
    output_path: str,
) -> None:
    """
    Render the aggregated data as an HTML report.

    Args:
        error_counts: Map of error message to count.
        api_latency: Map of endpoint to average ms.
        active_sessions: Number of currently active user sessions.
        output_path: Destination file path for the HTML report.
    """
    lines: List[str] = [
        "<html>",
        "<head><title>System Report</title></head>",
        "<body>",
        "<h1>Error Summary</h1>",
        "<ul>",
    ]

    for msg, count in error_counts.items():
        lines.append(f"<li><b>{msg}</b>: {count} occurrences</li>")

    lines.extend([
        "</ul>",
        "<h2>API Latency</h2>",
        "<table border='1'>",
        "<tr><th>Endpoint</th><th>Avg (ms)</th></tr>",
    ])

    for endpoint, avg_ms in api_latency.items():
        lines.append(f"<tr><td>{endpoint}</td><td>{round(avg_ms, 1)}</td></tr>")

    lines.extend([
        "</table>",
        "<h2>Active Sessions</h2>",
        f"<p>{active_sessions} user(s) currently active</p>",
        "</body>",
        "</html>",
    ])

    with open(output_path, "w") as fh:
        fh.write("\n".join(lines))


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def run_pipeline() -> None:
    """
    Execute the full ETL pipeline: extract, transform, load, and report.
    """
    config = get_config()
    log_path = config["log_file"]
    db_path = config["db_path"]

    print(
        f"Connecting to {config['db_host']}:{config['db_port']} "
        f"as {config['db_user']}..."
    )

    # EXTRACT
    entries = extract_log_entries(log_path)

    # TRANSFORM
    error_counts = aggregate_errors(entries["errors"])
    api_latency = aggregate_api_latency(entries["api_calls"])
    active_sessions = track_active_sessions(entries["user_actions"])

    # LOAD — database
    conn = sqlite3.connect(db_path)
    try:
        init_database(conn)
        persist_error_counts(conn, error_counts)
        persist_api_metrics(conn, api_latency)
        conn.commit()
    finally:
        conn.close()

    # LOAD — report
    generate_html_report(error_counts, api_latency, active_sessions, "report.html")

    print(f"Job finished at {datetime.datetime.now().isoformat()}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Create sample log if it doesn't exist (for demo / testing)
    config = get_config()
    if not os.path.exists(config["log_file"]):
        sample_lines = [
            "2024-01-01 12:00:00 INFO User 42 logged in",
            "2024-01-01 12:05:00 ERROR Database timeout",
            "2024-01-01 12:05:05 ERROR Database timeout",
            "2024-01-01 12:08:00 INFO API /users/profile took 250ms",
            "2024-01-01 12:09:00 WARN Memory usage at 87%",
            "2024-01-01 12:10:00 INFO User 42 logged out",
        ]
        with open(config["log_file"], "w") as fh:
            fh.write("\n".join(sample_lines) + "\n")

    run_pipeline()