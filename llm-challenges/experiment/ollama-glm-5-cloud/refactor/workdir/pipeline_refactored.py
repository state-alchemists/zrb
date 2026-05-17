"""Log processing pipeline with ETL architecture.

Processes server logs to generate metrics reports and populate a SQLite database.
"""

from __future__ import annotations

import datetime
import os
import re
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal


@dataclass(frozen=True, slots=True)
class Config:
    """Configuration loaded from environment variables."""

    db_path: Path
    log_file: Path
    db_host: str
    db_port: int
    db_user: str
    db_pass: str

    @classmethod
    def from_env(cls) -> Config:
        """Load configuration from environment variables with defaults."""
        return cls(
            db_path=Path(os.environ.get("DB_PATH", "metrics.db")),
            log_file=Path(os.environ.get("LOG_FILE", "server.log")),
            db_host=os.environ.get("DB_HOST", "localhost"),
            db_port=int(os.environ.get("DB_PORT", "5432")),
            db_user=os.environ.get("DB_USER", "admin"),
            db_pass=os.environ.get("DB_PASS", "password123"),
        )


@dataclass(frozen=True, slots=True)
class ErrorEntry:
    """Represents an ERROR log entry."""

    timestamp: str
    message: str


@dataclass(frozen=True, slots=True)
class UserActionEntry:
    """Represents a User action log entry."""

    timestamp: str
    user_id: str
    action: str


@dataclass(frozen=True, slots=True)
class ApiCallEntry:
    """Represents an API call log entry."""

    timestamp: str
    endpoint: str
    duration_ms: int


@dataclass(frozen=True, slots=True)
class WarningEntry:
    """Represents a WARN log entry."""

    timestamp: str
    message: str


@dataclass
class LogEntries:
    """Container for all parsed log entries."""

    errors: list[ErrorEntry] = field(default_factory=list)
    user_actions: list[UserActionEntry] = field(default_factory=list)
    api_calls: list[ApiCallEntry] = field(default_factory=list)
    warnings: list[WarningEntry] = field(default_factory=list)


# Regex patterns for log parsing
_ERROR_PATTERN = re.compile(
    r"^(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) ERROR (?P<message>.+)$"
)
_USER_ACTION_PATTERN = re.compile(
    r"^(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) INFO User (?P<user_id>\S+) (?P<action>.+)$"
)
_API_CALL_PATTERN = re.compile(
    r"^(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) INFO API (?P<endpoint>\S+) took (?P<duration>\d+)ms$"
)
_WARNING_PATTERN = re.compile(
    r"^(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) WARN (?P<message>.+)$"
)


def parse_log_line(line: str) -> ErrorEntry | UserActionEntry | ApiCallEntry | WarningEntry | None:
    """Parse a single log line into a typed entry.

    Args:
        line: Raw log line string.

    Returns:
        Parsed entry if line matches a known pattern, None otherwise.
    """
    stripped = line.strip()
    if not stripped:
        return None

    # Try each pattern in order of specificity
    if match := _API_CALL_PATTERN.match(stripped):
        return ApiCallEntry(
            timestamp=match.group("timestamp"),
            endpoint=match.group("endpoint"),
            duration_ms=int(match.group("duration")),
        )

    if match := _USER_ACTION_PATTERN.match(stripped):
        return UserActionEntry(
            timestamp=match.group("timestamp"),
            user_id=match.group("user_id"),
            action=match.group("action").strip(),
        )

    if match := _ERROR_PATTERN.match(stripped):
        return ErrorEntry(
            timestamp=match.group("timestamp"),
            message=match.group("message").strip(),
        )

    if match := _WARNING_PATTERN.match(stripped):
        return WarningEntry(
            timestamp=match.group("timestamp"),
            message=match.group("message").strip(),
        )

    return None


def extract_log_entries(log_file: Path) -> LogEntries:
    """Read log file and parse all entries.

    Args:
        log_file: Path to the log file.

    Returns:
        Container with all parsed entries categorized by type.
    """
    entries = LogEntries()

    if not log_file.exists():
        return entries

    with log_file.open("r") as f:
        for line in f:
            entry = parse_log_line(line)
            if entry is None:
                continue

            if isinstance(entry, ErrorEntry):
                entries.errors.append(entry)
            elif isinstance(entry, UserActionEntry):
                entries.user_actions.append(entry)
            elif isinstance(entry, ApiCallEntry):
                entries.api_calls.append(entry)
            elif isinstance(entry, WarningEntry):
                entries.warnings.append(entry)

    return entries


def aggregate_errors(errors: list[ErrorEntry]) -> dict[str, int]:
    """Aggregate error counts by message.

    Args:
        errors: List of error entries.

    Returns:
        Dictionary mapping error message to occurrence count.
    """
    counts: dict[str, int] = {}
    for error in errors:
        counts[error.message] = counts.get(error.message, 0) + 1
    return counts


def calculate_api_latency(api_calls: list[ApiCallEntry]) -> dict[str, float]:
    """Calculate average latency per API endpoint.

    Args:
        api_calls: List of API call entries.

    Returns:
        Dictionary mapping endpoint to average latency in milliseconds.
    """
    latencies: dict[str, list[int]] = {}
    for call in api_calls:
        latencies.setdefault(call.endpoint, []).append(call.duration_ms)

    return {
        endpoint: sum(times) / len(times)
        for endpoint, times in latencies.items()
    }


def track_active_sessions(user_actions: list[UserActionEntry]) -> dict[str, str]:
    """Track active sessions from user actions.

    Args:
        user_actions: List of user action entries.

    Returns:
        Dictionary mapping user ID to login timestamp for active sessions.
    """
    sessions: dict[str, str] = {}
    for action in user_actions:
        if "logged in" in action.action:
            sessions[action.user_id] = action.timestamp
        elif "logged out" in action.action and action.user_id in sessions:
            del sessions[action.user_id]
    return sessions


def init_database(conn: sqlite3.Connection) -> None:
    """Initialize database tables.

    Args:
        conn: SQLite database connection.
    """
    cursor = conn.cursor()
    cursor.execute(
        "CREATE TABLE IF NOT EXISTS errors (dt TEXT, message TEXT, count INTEGER)"
    )
    cursor.execute(
        "CREATE TABLE IF NOT EXISTS api_metrics (dt TEXT, endpoint TEXT, avg_ms REAL)"
    )


def save_error_metrics(
    conn: sqlite3.Connection, error_counts: dict[str, int]
) -> None:
    """Save error metrics to database using parameterized queries.

    Args:
        conn: SQLite database connection.
        error_counts: Dictionary of error message to count.
    """
    cursor = conn.cursor()
    timestamp = datetime.datetime.now().isoformat()

    for message, count in error_counts.items():
        cursor.execute(
            "INSERT INTO errors (dt, message, count) VALUES (?, ?, ?)",
            (timestamp, message, count),
        )


def save_api_metrics(
    conn: sqlite3.Connection, api_latencies: dict[str, float]
) -> None:
    """Save API metrics to database using parameterized queries.

    Args:
        conn: SQLite database connection.
        api_latencies: Dictionary of endpoint to average latency.
    """
    cursor = conn.cursor()
    timestamp = datetime.datetime.now().isoformat()

    for endpoint, avg_ms in api_latencies.items():
        cursor.execute(
            "INSERT INTO api_metrics (dt, endpoint, avg_ms) VALUES (?, ?, ?)",
            (timestamp, endpoint, avg_ms),
        )


def generate_html_report(
    error_counts: dict[str, int],
    api_latencies: dict[str, float],
    active_session_count: int,
) -> str:
    """Generate HTML report from metrics.

    Args:
        error_counts: Dictionary of error message to count.
        api_latencies: Dictionary of endpoint to average latency.
        active_session_count: Number of currently active sessions.

    Returns:
        Complete HTML document as a string.
    """
    lines = [
        "<html>",
        "<head><title>System Report</title></head>",
        "<body>",
        "<h1>Error Summary</h1>",
        "<ul>",
    ]

    for message, count in error_counts.items():
        lines.append(f"<li><b>{message}</b>: {count} occurrences</li>")

    lines.extend([
        "</ul>",
        "<h2>API Latency</h2>",
        "<table border='1'>",
        "<tr><th>Endpoint</th><th>Avg (ms)</th></tr>",
    ])

    for endpoint, avg_ms in api_latencies.items():
        lines.append(f"<tr><td>{endpoint}</td><td>{avg_ms:.1f}</td></tr>")

    lines.extend([
        "</table>",
        "<h2>Active Sessions</h2>",
        f"<p>{active_session_count} user(s) currently active</p>",
        "</body>",
        "</html>",
    ])

    return "\n".join(lines)


def create_sample_log(log_file: Path) -> None:
    """Create sample log file for demonstration.

    Args:
        log_file: Path where the sample log should be created.
    """
    with log_file.open("w") as f:
        f.write("2024-01-01 12:00:00 INFO User 42 logged in\n")
        f.write("2024-01-01 12:05:00 ERROR Database timeout\n")
        f.write("2024-01-01 12:05:05 ERROR Database timeout\n")
        f.write("2024-01-01 12:08:00 INFO API /users/profile took 250ms\n")
        f.write("2024-01-01 12:09:00 WARN Memory usage at 87%\n")
        f.write("2024-01-01 12:10:00 INFO User 42 logged out\n")


def main() -> None:
    """Run the ETL pipeline."""
    config = Config.from_env()

    # Ensure log file exists (create sample for demo)
    if not config.log_file.exists():
        create_sample_log(config.log_file)

    # EXTRACT: Parse log file
    entries = extract_log_entries(config.log_file)

    # TRANSFORM: Aggregate metrics
    error_counts = aggregate_errors(entries.errors)
    api_latencies = calculate_api_latency(entries.api_calls)
    active_sessions = track_active_sessions(entries.user_actions)

    # LOAD: Save to database
    print(f"Connecting to {config.db_host}:{config.db_port} as {config.db_user}...")

    with sqlite3.connect(config.db_path) as conn:
        init_database(conn)
        save_error_metrics(conn, error_counts)
        save_api_metrics(conn, api_latencies)

    # Generate report
    report = generate_html_report(
        error_counts=error_counts,
        api_latencies=api_latencies,
        active_session_count=len(active_sessions),
    )

    report_path = Path("report.html")
    report_path.write_text(report)

    print(f"Job finished at {datetime.datetime.now()}")


if __name__ == "__main__":
    main()