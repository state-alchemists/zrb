"""Log processing pipeline for server metrics.

Extracts data from server logs, transforms it into aggregated metrics,
and loads results into a SQLite database and HTML report.

Environment Variables:
    DB_PATH: Path to SQLite database file (default: metrics.db)
    LOG_FILE: Path to server log file (default: server.log)
    DB_HOST: Database host for logging (default: localhost)
    DB_PORT: Database port for logging (default: 5432)
    DB_USER: Database user for logging (default: admin)
    DB_PASS: Database password (should be set via env, no default)
"""

from __future__ import annotations

import datetime
import os
import re
import sqlite3
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Config:
    """Configuration loaded from environment variables."""

    db_path: str
    log_file: str
    db_host: str
    db_port: int
    db_user: str
    db_pass: str

    @classmethod
    def from_env(cls) -> "Config":
        """Load configuration from environment variables with defaults."""
        return cls(
            db_path=os.getenv("DB_PATH", "metrics.db"),
            log_file=os.getenv("LOG_FILE", "server.log"),
            db_host=os.getenv("DB_HOST", "localhost"),
            db_port=int(os.getenv("DB_PORT", "5432")),
            db_user=os.getenv("DB_USER", "admin"),
            db_pass=os.getenv("DB_PASS", ""),
        )


@dataclass
class LogEntry:
    """Base class for parsed log entries."""

    timestamp: str
    level: str


@dataclass
class ErrorEntry(LogEntry):
    """An error log entry with message."""

    message: str


@dataclass
class UserActionEntry(LogEntry):
    """A user action log entry (login/logout)."""

    user_id: str
    action: str


@dataclass
class ApiCallEntry(LogEntry):
    """An API call log entry with latency."""

    endpoint: str
    latency_ms: int


@dataclass
class WarningEntry(LogEntry):
    """A warning log entry with message."""

    message: str


@dataclass
class ParsedLogs:
    """Container for all parsed log data."""

    errors: list[ErrorEntry] = field(default_factory=list)
    user_actions: list[UserActionEntry] = field(default_factory=list)
    api_calls: list[ApiCallEntry] = field(default_factory=list)
    warnings: list[WarningEntry] = field(default_factory=list)


# Regex pattern for log line parsing
# Format: YYYY-MM-DD HH:MM:SS LEVEL <rest>
LOG_PATTERN = re.compile(
    r"^(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\s+"
    r"(?P<level>ERROR|INFO|WARN)\s+"
    r"(?P<content>.*)$"
)

# User action pattern: "User <id> <action>"
USER_PATTERN = re.compile(r"^User\s+(?P<user_id>\S+)\s+(?P<action>.+)$")

# API call pattern: "API <endpoint> took <ms>ms"
API_PATTERN = re.compile(r"^API\s+(?P<endpoint>\S+)(?:\s+took\s+(?P<latency>\d+)ms)?$")


def parse_log_line(line: str) -> Optional[LogEntry]:
    """Parse a single log line into a typed entry.

    Args:
        line: Raw log line string.

    Returns:
        Typed LogEntry subclass instance, or None if line cannot be parsed.
    """
    match = LOG_PATTERN.match(line.strip())
    if not match:
        return None

    timestamp = match.group("timestamp")
    level = match.group("level")
    content = match.group("content")

    if level == "ERROR":
        return ErrorEntry(timestamp=timestamp, level=level, message=content)

    if level == "WARN":
        return WarningEntry(timestamp=timestamp, level=level, message=content)

    if level == "INFO":
        # Check for user action
        user_match = USER_PATTERN.match(content)
        if user_match:
            return UserActionEntry(
                timestamp=timestamp,
                level=level,
                user_id=user_match.group("user_id"),
                action=user_match.group("action").strip(),
            )

        # Check for API call
        api_match = API_PATTERN.match(content)
        if api_match:
            latency = int(api_match.group("latency") or "0")
            return ApiCallEntry(
                timestamp=timestamp,
                level=level,
                endpoint=api_match.group("endpoint"),
                latency_ms=latency,
            )

    return None


def extract_logs(config: Config) -> ParsedLogs:
    """Extract and parse log entries from the log file.

    Args:
        config: Configuration containing the log file path.

    Returns:
        ParsedLogs container with all parsed entries.
    """
    parsed = ParsedLogs()

    if not os.path.exists(config.log_file):
        return parsed

    with open(config.log_file, "r", encoding="utf-8") as f:
        for line in f:
            entry = parse_log_line(line)
            if entry is None:
                continue

            if isinstance(entry, ErrorEntry):
                parsed.errors.append(entry)
            elif isinstance(entry, UserActionEntry):
                parsed.user_actions.append(entry)
            elif isinstance(entry, ApiCallEntry):
                parsed.api_calls.append(entry)
            elif isinstance(entry, WarningEntry):
                parsed.warnings.append(entry)

    return parsed


def compute_error_counts(errors: list[ErrorEntry]) -> dict[str, int]:
    """Compute frequency counts for error messages.

    Args:
        errors: List of error entries.

    Returns:
        Dictionary mapping error message to occurrence count.
    """
    counts: dict[str, int] = {}
    for error in errors:
        counts[error.message] = counts.get(error.message, 0) + 1
    return counts


def compute_active_sessions(user_actions: list[UserActionEntry]) -> set[str]:
    """Compute set of currently active user sessions.

    A session is active if the user logged in without a subsequent logout.

    Args:
        user_actions: List of user action entries in chronological order.

    Returns:
        Set of user IDs with active sessions.
    """
    active: set[str] = set()
    for action in user_actions:
        if "logged in" in action.action and "logged out" not in action.action:
            active.add(action.user_id)
        elif "logged out" in action.action:
            active.discard(action.user_id)
    return active


def compute_endpoint_latency(api_calls: list[ApiCallEntry]) -> dict[str, list[int]]:
    """Group API latencies by endpoint.

    Args:
        api_calls: List of API call entries.

    Returns:
        Dictionary mapping endpoint to list of latency values.
    """
    stats: dict[str, list[int]] = {}
    for call in api_calls:
        stats.setdefault(call.endpoint, []).append(call.latency_ms)
    return stats


def create_tables(conn: sqlite3.Connection) -> None:
    """Create database tables if they do not exist.

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


def insert_error_metrics(
    conn: sqlite3.Connection, error_counts: dict[str, int]
) -> None:
    """Insert error counts into database using parameterized queries.

    Args:
        conn: SQLite database connection.
        error_counts: Dictionary mapping error message to count.
    """
    cursor = conn.cursor()
    timestamp = datetime.datetime.now().isoformat()

    for message, count in error_counts.items():
        # Parameterized query prevents SQL injection
        cursor.execute(
            "INSERT INTO errors (dt, message, count) VALUES (?, ?, ?)",
            (timestamp, message, count),
        )


def insert_api_metrics(
    conn: sqlite3.Connection, endpoint_latency: dict[str, list[int]]
) -> None:
    """Insert API latency metrics into database using parameterized queries.

    Args:
        conn: SQLite database connection.
        endpoint_latency: Dictionary mapping endpoint to latency list.
    """
    cursor = conn.cursor()
    timestamp = datetime.datetime.now().isoformat()

    for endpoint, latencies in endpoint_latency.items():
        avg_latency = sum(latencies) / len(latencies) if latencies else 0.0
        # Parameterized query prevents SQL injection
        cursor.execute(
            "INSERT INTO api_metrics (dt, endpoint, avg_ms) VALUES (?, ?, ?)",
            (timestamp, endpoint, avg_latency),
        )


def load_to_database(
    config: Config,
    error_counts: dict[str, int],
    endpoint_latency: dict[str, list[int]],
) -> None:
    """Load transformed data into SQLite database.

    Args:
        config: Configuration containing database path.
        error_counts: Dictionary mapping error message to count.
        endpoint_latency: Dictionary mapping endpoint to latency list.
    """
    print(f"Connecting to {config.db_host}:{config.db_port} as {config.db_user}...")

    conn = sqlite3.connect(config.db_path)
    try:
        create_tables(conn)
        insert_error_metrics(conn, error_counts)
        insert_api_metrics(conn, endpoint_latency)
        conn.commit()
    finally:
        conn.close()


def generate_html_report(
    error_counts: dict[str, int],
    endpoint_latency: dict[str, list[int]],
    active_sessions: set[str],
) -> str:
    """Generate HTML report from aggregated metrics.

    Args:
        error_counts: Dictionary mapping error message to count.
        endpoint_latency: Dictionary mapping endpoint to latency list.
        active_sessions: Set of user IDs with active sessions.

    Returns:
        Complete HTML document as string.
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

    lines.append("</ul>")
    lines.append("<h2>API Latency</h2>")
    lines.append("<table border='1'>")
    lines.append("<tr><th>Endpoint</th><th>Avg (ms)</th></tr>")

    for endpoint, latencies in endpoint_latency.items():
        avg = round(sum(latencies) / len(latencies), 1) if latencies else 0.0
        lines.append(f"<tr><td>{endpoint}</td><td>{avg}</td></tr>")

    lines.append("</table>")
    lines.append("<h2>Active Sessions</h2>")
    lines.append(f"<p>{len(active_sessions)} user(s) currently active</p>")
    lines.append("</body>")
    lines.append("</html>")

    return "\n".join(lines)


def write_report(report_path: str, html_content: str) -> None:
    """Write HTML report to file.

    Args:
        report_path: Path to output HTML file.
        html_content: Complete HTML document string.
    """
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(html_content)


def run_pipeline(report_path: str = "report.html") -> None:
    """Execute the complete ETL pipeline.

    Orchestrates extract → transform → load phases for log processing.

    Args:
        report_path: Path to output HTML report file.
    """
    config = Config.from_env()

    # Extract
    logs = extract_logs(config)

    # Transform
    error_counts = compute_error_counts(logs.errors)
    active_sessions = compute_active_sessions(logs.user_actions)
    endpoint_latency = compute_endpoint_latency(logs.api_calls)

    # Load
    load_to_database(config, error_counts, endpoint_latency)

    # Generate and write report
    html = generate_html_report(error_counts, endpoint_latency, active_sessions)
    write_report(report_path, html)

    print(f"Job finished at {datetime.datetime.now()}")


if __name__ == "__main__":
    # Create sample log file for testing if it doesn't exist
    config = Config.from_env()
    if not os.path.exists(config.log_file):
        with open(config.log_file, "w", encoding="utf-8") as f:
            f.write("2024-01-01 12:00:00 INFO User 42 logged in\n")
            f.write("2024-01-01 12:05:00 ERROR Database timeout\n")
            f.write("2024-01-01 12:05:05 ERROR Database timeout\n")
            f.write("2024-01-01 12:08:00 INFO API /users/profile took 250ms\n")
            f.write("2024-01-01 12:09:00 WARN Memory usage at 87%\n")
            f.write("2024-01-01 12:10:00 INFO User 42 logged out\n")

    run_pipeline()