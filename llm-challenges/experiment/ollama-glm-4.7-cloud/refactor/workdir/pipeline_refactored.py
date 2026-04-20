"""Log processing pipeline with ETL pattern.

Extracts server logs, transforms them into metrics, and loads results
into a database while generating an HTML report.
"""

import os
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional

# Environment variable configuration
DB_PATH = os.getenv("DB_PATH", "metrics.db")
LOG_FILE = os.getenv("LOG_FILE", "server.log")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_USER = os.getenv("DB_USER", "admin")
DB_PASS = os.getenv("DB_PASS", "password123")
REPORT_FILE = os.getenv("REPORT_FILE", "report.html")


@dataclass
class LogEntry:
    """Represents a parsed log line."""

    timestamp: datetime
    level: str
    message: str


@dataclass
class UserAction:
    """Represents a user login/logout action."""

    timestamp: datetime
    user_id: str
    action: str


@dataclass
class ApiCall:
    """Represents an API call with latency."""

    timestamp: datetime
    endpoint: str
    duration_ms: int


@dataclass
class ErrorSummary:
    """Aggregated error statistics."""

    message: str
    count: int


@dataclass
class ApiMetrics:
    """Aggregated API performance metrics."""

    endpoint: str
    avg_duration_ms: float


def parse_log_line(line: str) -> Optional[LogEntry]:
    """Parse a single log line into a LogEntry.

    Args:
        line: Raw log line string.

    Returns:
        LogEntry if parsing succeeds, None otherwise.
    """
    pattern = r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) (\w+) (.+)$"
    match = re.match(pattern, line.strip())
    if not match:
        return None

    timestamp_str, level, message = match.groups()
    try:
        timestamp = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None

    return LogEntry(timestamp=timestamp, level=level, message=message)


def extract_user_action(entry: LogEntry) -> Optional[UserAction]:
    """Extract user action from a log entry.

    Args:
        entry: Parsed log entry.

    Returns:
        UserAction if entry contains user action, None otherwise.
    """
    if entry.level != "INFO" or "User" not in entry.message:
        return None

    pattern = r"User (\d+) (.+)"
    match = re.search(pattern, entry.message)
    if not match:
        return None

    user_id, action = match.groups()
    return UserAction(timestamp=entry.timestamp, user_id=user_id, action=action)


def extract_api_call(entry: LogEntry) -> Optional[ApiCall]:
    """Extract API call from a log entry.

    Args:
        entry: Parsed log entry.

    Returns:
        ApiCall if entry contains API call, None otherwise.
    """
    if entry.level != "INFO" or "API" not in entry.message:
        return None

    endpoint_pattern = r"API (/[\w/]+)"
    duration_pattern = r"took (\d+)ms"

    endpoint_match = re.search(endpoint_pattern, entry.message)
    duration_match = re.search(duration_pattern, entry.message)

    if not endpoint_match:
        return None

    endpoint = endpoint_match.group(1)
    duration_ms = int(duration_match.group(1)) if duration_match else 0

    return ApiCall(
        timestamp=entry.timestamp,
        endpoint=endpoint,
        duration_ms=duration_ms,
    )


def extract_log_data(log_file: str) -> tuple[List[LogEntry], Dict[str, datetime], List[ApiCall]]:
    """Extract and parse log data from file.

    Args:
        log_file: Path to log file.

    Returns:
        Tuple of (all log entries, active sessions dict, API calls list).
    """
    if not os.path.exists(log_file):
        return [], {}, []

    entries: List[LogEntry] = []
    sessions: Dict[str, datetime] = {}
    api_calls: List[ApiCall] = []

    with open(log_file, "r") as f:
        for line in f:
            entry = parse_log_line(line)
            if not entry:
                continue

            entries.append(entry)

            user_action = extract_user_action(entry)
            if user_action:
                entries[-1] = entry  # Track all entries
                if "logged in" in user_action.action:
                    sessions[user_action.user_id] = user_action.timestamp
                elif "logged out" in user_action.action and user_action.user_id in sessions:
                    del sessions[user_action.user_id]

            api_call = extract_api_call(entry)
            if api_call:
                api_calls.append(api_call)

    return entries, sessions, api_calls


def transform_errors(entries: List[LogEntry]) -> List[ErrorSummary]:
    """Aggregate error messages with occurrence counts.

    Args:
        entries: List of parsed log entries.

    Returns:
        List of error summaries sorted by count descending.
    """
    error_counts: Dict[str, int] = {}

    for entry in entries:
        if entry.level == "ERROR":
            error_counts[entry.message] = error_counts.get(entry.message, 0) + 1

    return [
        ErrorSummary(message=msg, count=count)
        for msg, count in sorted(error_counts.items(), key=lambda x: x[1], reverse=True)
    ]


def transform_api_metrics(api_calls: List[ApiCall]) -> List[ApiMetrics]:
    """Calculate average latency per API endpoint.

    Args:
        api_calls: List of API call records.

    Returns:
        List of API metrics with average durations.
    """
    endpoint_times: Dict[str, List[int]] = {}

    for call in api_calls:
        endpoint_times.setdefault(call.endpoint, []).append(call.duration_ms)

    return [
        ApiMetrics(
            endpoint=endpoint,
            avg_duration_ms=sum(times) / len(times),
        )
        for endpoint, times in endpoint_times.items()
    ]


def create_database_schema(conn: sqlite3.Connection) -> None:
    """Create database tables if they don't exist.

    Args:
        conn: SQLite database connection.
    """
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS errors (
            dt TEXT,
            message TEXT,
            count INTEGER
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS api_metrics (
            dt TEXT,
            endpoint TEXT,
            avg_ms REAL
        )
        """
    )


def load_errors(conn: sqlite3.Connection, errors: List[ErrorSummary]) -> None:
    """Insert error summaries into database.

    Args:
        conn: SQLite database connection.
        errors: List of error summaries to insert.
    """
    cursor = conn.cursor()
    now = datetime.now().isoformat()

    for error in errors:
        cursor.execute(
            "INSERT INTO errors (dt, message, count) VALUES (?, ?, ?)",
            (now, error.message, error.count),
        )


def load_api_metrics(conn: sqlite3.Connection, metrics: List[ApiMetrics]) -> None:
    """Insert API metrics into database.

    Args:
        conn: SQLite database connection.
        metrics: List of API metrics to insert.
    """
    cursor = conn.cursor()
    now = datetime.now().isoformat()

    for metric in metrics:
        cursor.execute(
            "INSERT INTO api_metrics (dt, endpoint, avg_ms) VALUES (?, ?, ?)",
            (now, metric.endpoint, metric.avg_duration_ms),
        )


def load_to_db(
    db_path: str,
    errors: List[ErrorSummary],
    api_metrics: List[ApiMetrics],
) -> None:
    """Load transformed data into SQLite database.

    Args:
        db_path: Path to SQLite database file.
        errors: Error summaries to store.
        api_metrics: API metrics to store.
    """
    conn = sqlite3.connect(db_path)
    try:
        create_database_schema(conn)
        load_errors(conn, errors)
        load_api_metrics(conn, api_metrics)
        conn.commit()
    finally:
        conn.close()


def generate_html_report(
    errors: List[ErrorSummary],
    api_metrics: List[ApiMetrics],
    active_sessions: int,
    output_file: str,
) -> None:
    """Generate HTML report with error summary, API latency, and session count.

    Args:
        errors: List of error summaries.
        api_metrics: List of API metrics.
        active_sessions: Number of currently active sessions.
        output_file: Path to output HTML file.
    """
    lines = [
        "<html>",
        "<head><title>System Report</title></head>",
        "<body>",
        "<h1>Error Summary</h1>",
        "<ul>",
    ]

    for error in errors:
        lines.append(f"<li><b>{error.message}</b>: {error.count} occurrences</li>")

    lines.extend([
        "</ul>",
        "<h2>API Latency</h2>",
        "<table border='1'>",
        "<tr><th>Endpoint</th><th>Avg (ms)</th></tr>",
    ])

    for metric in api_metrics:
        lines.append(
            f"<tr><td>{metric.endpoint}</td><td>{round(metric.avg_duration_ms, 1)}</td></tr>"
        )

    lines.extend([
        "</table>",
        "<h2>Active Sessions</h2>",
        f"<p>{active_sessions} user(s) currently active</p>",
        "</body>",
        "</html>",
    ])

    with open(output_file, "w") as f:
        f.write("\n".join(lines))


def create_sample_log_file(log_file: str) -> None:
    """Create a sample log file for testing.

    Args:
        log_file: Path to log file to create.
    """
    sample_lines = [
        "2024-01-01 12:00:00 INFO User 42 logged in",
        "2024-01-01 12:05:00 ERROR Database timeout",
        "2024-01-01 12:05:05 ERROR Database timeout",
        "2024-01-01 12:08:00 INFO API /users/profile took 250ms",
        "2024-01-01 12:09:00 WARN Memory usage at 87%",
        "2024-01-01 12:10:00 INFO User 42 logged out",
    ]

    with open(log_file, "w") as f:
        f.write("\n".join(sample_lines) + "\n")


def main() -> None:
    """Main ETL pipeline execution."""
    # Create sample log if it doesn't exist
    if not os.path.exists(LOG_FILE):
        create_sample_log_file(LOG_FILE)

    print(f"Processing log file: {LOG_FILE}")
    print(f"Database: {DB_PATH}")
    print(f"Connecting to {DB_HOST}:{DB_PORT} as {DB_USER}...")

    # Extract
    entries, sessions, api_calls = extract_log_data(LOG_FILE)

    # Transform
    errors = transform_errors(entries)
    api_metrics = transform_api_metrics(api_calls)

    # Load
    load_to_db(DB_PATH, errors, api_metrics)

    # Generate report
    generate_html_report(errors, api_metrics, len(sessions), REPORT_FILE)

    print(f"Job finished at {datetime.now()}")
    print(f"Report generated: {REPORT_FILE}")


if __name__ == "__main__":
    main()