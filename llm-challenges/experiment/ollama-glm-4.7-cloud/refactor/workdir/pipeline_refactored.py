"""Server log processing pipeline with ETL pattern.

Extracts log entries, transforms them into metrics, loads into database,
and generates an HTML report.
"""

import os
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional


@dataclass
class LogEntry:
    """Represents a parsed log line."""
    timestamp: str
    level: str
    message: str
    user_id: Optional[str] = None
    action: Optional[str] = None
    endpoint: Optional[str] = None
    duration_ms: Optional[int] = None


@dataclass
class ErrorSummary:
    """Aggregated error statistics."""
    message: str
    count: int


@dataclass
class ApiMetric:
    """API performance metrics."""
    endpoint: str
    avg_ms: float


def get_config() -> Dict[str, str]:
    """Load configuration from environment variables.

    Returns:
        Dictionary containing configuration values with defaults.
    """
    return {
        "db_path": os.getenv("DB_PATH", "metrics.db"),
        "log_file": os.getenv("LOG_FILE", "server.log"),
        "db_host": os.getenv("DB_HOST", "localhost"),
        "db_port": os.getenv("DB_PORT", "5432"),
        "db_user": os.getenv("DB_USER", "admin"),
        "db_pass": os.getenv("DB_PASS", "password123"),
    }


def parse_log_line(line: str) -> Optional[LogEntry]:
    """Parse a single log line using regex patterns.

    Args:
        line: Raw log line string.

    Returns:
        LogEntry if parsing succeeds, None otherwise.
    """
    # Pattern: YYYY-MM-DD HH:MM:SS LEVEL message...
    timestamp_pattern = r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) (\w+) (.+)$"
    match = re.match(timestamp_pattern, line.strip())
    if not match:
        return None

    timestamp, level, message = match.groups()

    entry = LogEntry(timestamp=timestamp, level=level, message=message)

    # Parse user action: "User 42 logged in"
    user_match = re.search(r"User (\d+) (.+)", message)
    if user_match:
        entry.user_id = user_match.group(1)
        entry.action = user_match.group(2)

    # Parse API call: "API /users/profile took 250ms"
    api_match = re.search(r"API (\S+) took (\d+)ms", message)
    if api_match:
        entry.endpoint = api_match.group(1)
        entry.duration_ms = int(api_match.group(2))

    return entry


def extract_log_entries(log_file: str) -> List[LogEntry]:
    """Extract and parse all log entries from the log file.

    Args:
        log_file: Path to the log file.

    Returns:
        List of parsed LogEntry objects.
    """
    entries = []
    if not os.path.exists(log_file):
        return entries

    with open(log_file, "r") as f:
        for line in f:
            entry = parse_log_line(line)
            if entry:
                entries.append(entry)

    return entries


def transform_errors(entries: List[LogEntry]) -> List[ErrorSummary]:
    """Aggregate error messages with occurrence counts.

    Args:
        entries: List of parsed log entries.

    Returns:
        List of ErrorSummary objects sorted by count (descending).
    """
    error_counts: Dict[str, int] = {}
    for entry in entries:
        if entry.level == "ERROR":
            error_counts[entry.message] = error_counts.get(entry.message, 0) + 1

    return [
        ErrorSummary(message=msg, count=count)
        for msg, count in sorted(error_counts.items(), key=lambda x: x[1], reverse=True)
    ]


def transform_api_metrics(entries: List[LogEntry]) -> List[ApiMetric]:
    """Calculate average latency per API endpoint.

    Args:
        entries: List of parsed log entries.

    Returns:
        List of ApiMetric objects.
    """
    endpoint_times: Dict[str, List[int]] = {}
    for entry in entries:
        if entry.endpoint and entry.duration_ms is not None:
            endpoint_times.setdefault(entry.endpoint, []).append(entry.duration_ms)

    return [
        ApiMetric(endpoint=ep, avg_ms=sum(times) / len(times))
        for ep, times in endpoint_times.items()
    ]


def transform_active_sessions(entries: List[LogEntry]) -> Dict[str, str]:
    """Track active user sessions based on login/logout events.

    Args:
        entries: List of parsed log entries.

    Returns:
        Dictionary mapping user_id to login timestamp.
    """
    sessions: Dict[str, str] = {}
    for entry in entries:
        if entry.user_id and entry.action:
            if "logged in" in entry.action:
                sessions[entry.user_id] = entry.timestamp
            elif "logged out" in entry.action and entry.user_id in sessions:
                del sessions[entry.user_id]

    return sessions


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
    """Insert error summaries into the database using parameterized queries.

    Args:
        conn: SQLite database connection.
        errors: List of ErrorSummary objects to insert.
    """
    cursor = conn.cursor()
    now = datetime.now().isoformat()
    for error in errors:
        cursor.execute(
            "INSERT INTO errors (dt, message, count) VALUES (?, ?, ?)",
            (now, error.message, error.count),
        )


def load_api_metrics(conn: sqlite3.Connection, metrics: List[ApiMetric]) -> None:
    """Insert API metrics into the database using parameterized queries.

    Args:
        conn: SQLite database connection.
        metrics: List of ApiMetric objects to insert.
    """
    cursor = conn.cursor()
    now = datetime.now().isoformat()
    for metric in metrics:
        cursor.execute(
            "INSERT INTO api_metrics (dt, endpoint, avg_ms) VALUES (?, ?, ?)",
            (now, metric.endpoint, metric.avg_ms),
        )


def generate_html_report(
    errors: List[ErrorSummary],
    api_metrics: List[ApiMetric],
    active_sessions: Dict[str, str],
    output_path: str = "report.html",
) -> None:
    """Generate an HTML report with error summary, API latency, and session count.

    Args:
        errors: List of ErrorSummary objects.
        api_metrics: List of ApiMetric objects.
        active_sessions: Dictionary of active sessions.
        output_path: Path to write the HTML report.
    """
    html = "<html>\n<head><title>System Report</title></head>\n<body>\n"

    # Error Summary
    html += "<h1>Error Summary</h1>\n<ul>\n"
    for error in errors:
        html += f"<li><b>{error.message}</b>: {error.count} occurrences</li>\n"
    html += "</ul>\n"

    # API Latency
    html += "<h2>API Latency</h2>\n<table border='1'>\n"
    html += "<tr><th>Endpoint</th><th>Avg (ms)</th></tr>\n"
    for metric in api_metrics:
        html += f"<tr><td>{metric.endpoint}</td><td>{round(metric.avg_ms, 1)}</td></tr>\n"
    html += "</table>\n"

    # Active Sessions
    html += "<h2>Active Sessions</h2>\n"
    html += f"<p>{len(active_sessions)} user(s) currently active</p>\n"
    html += "</body>\n</html>"

    with open(output_path, "w") as f:
        f.write(html)


def create_sample_log_file(log_file: str) -> None:
    """Create a sample log file for testing if it doesn't exist.

    Args:
        log_file: Path to the log file.
    """
    if not os.path.exists(log_file):
        with open(log_file, "w") as f:
            f.write("2024-01-01 12:00:00 INFO User 42 logged in\n")
            f.write("2024-01-01 12:05:00 ERROR Database timeout\n")
            f.write("2024-01-01 12:05:05 ERROR Database timeout\n")
            f.write("2024-01-01 12:08:00 INFO API /users/profile took 250ms\n")
            f.write("2024-01-01 12:09:00 WARN Memory usage at 87%\n")
            f.write("2024-01-01 12:10:00 INFO User 42 logged out\n")


def main() -> None:
    """Main ETL pipeline: extract, transform, load, and report."""
    config = get_config()

    # Create sample log if needed
    create_sample_log_file(config["log_file"])

    print(f"Connecting to {config['db_host']}:{config['db_port']} as {config['db_user']}...")

    # Extract: Parse log file
    entries = extract_log_entries(config["log_file"])
    print(f"Parsed {len(entries)} log entries")

    # Transform: Aggregate metrics
    errors = transform_errors(entries)
    api_metrics = transform_api_metrics(entries)
    active_sessions = transform_active_sessions(entries)

    # Load: Store in database
    conn = sqlite3.connect(config["db_path"])
    create_database_schema(conn)
    load_errors(conn, errors)
    load_api_metrics(conn, api_metrics)
    conn.commit()
    conn.close()

    # Generate: HTML report
    generate_html_report(errors, api_metrics, active_sessions)

    print(f"Job finished at {datetime.now()}")


if __name__ == "__main__":
    main()