"""
Log processing pipeline for server metrics.

Extracts log entries, aggregates metrics, stores in database, and generates HTML report.
"""

import os
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional


# Configuration from environment variables with defaults
DB_PATH = os.getenv("DB_PATH", "metrics.db")
LOG_FILE = os.getenv("LOG_FILE", "server.log")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_USER = os.getenv("DB_USER", "admin")
DB_PASS = os.getenv("DB_PASS", "password123")
REPORT_OUTPUT = os.getenv("REPORT_OUTPUT", "report.html")


@dataclass
class LogEntry:
    """Represents a parsed log line."""
    timestamp: datetime
    level: str
    message: str
    user_id: Optional[str] = None
    action: Optional[str] = None
    endpoint: Optional[str] = None
    duration_ms: Optional[int] = None


@dataclass
class ErrorStats:
    """Aggregated error statistics."""
    message: str
    count: int


@dataclass
class ApiMetrics:
    """Aggregated API performance metrics."""
    endpoint: str
    avg_ms: float
    call_count: int


# Regex patterns for log parsing
LOG_PATTERN = re.compile(
    r'^(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) '
    r'(?P<level>\w+) '
    r'(?P<message>.*)$'
)

USER_ACTION_PATTERN = re.compile(r'User (?P<user_id>\d+) (?P<action>.+)$')
API_CALL_PATTERN = re.compile(r'API (?P<endpoint>/[^\s]+) took (?P<duration>\d+)ms$')


def parse_log_line(line: str) -> Optional[LogEntry]:
    """
    Parse a single log line into a structured LogEntry.

    Args:
        line: Raw log line string

    Returns:
        LogEntry if parsing succeeds, None otherwise
    """
    match = LOG_PATTERN.match(line.strip())
    if not match:
        return None

    timestamp_str = match.group("timestamp")
    level = match.group("level")
    message = match.group("message")

    try:
        timestamp = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None

    entry = LogEntry(timestamp=timestamp, level=level, message=message)

    # Parse user actions
    if level == "INFO" and "User" in message:
        user_match = USER_ACTION_PATTERN.match(message)
        if user_match:
            entry.user_id = user_match.group("user_id")
            entry.action = user_match.group("action")

    # Parse API calls
    if level == "INFO" and "API" in message:
        api_match = API_CALL_PATTERN.search(message)
        if api_match:
            entry.endpoint = api_match.group("endpoint")
            entry.duration_ms = int(api_match.group("duration"))

    return entry


def extract_log_data(log_path: str) -> List[LogEntry]:
    """
    Extract and parse all log entries from the log file.

    Args:
        log_path: Path to the log file

    Returns:
        List of parsed LogEntry objects
    """
    if not os.path.exists(log_path):
        return []

    entries = []
    with open(log_path, "r") as f:
        for line in f:
            entry = parse_log_line(line)
            if entry:
                entries.append(entry)

    return entries


def aggregate_errors(entries: List[LogEntry]) -> Dict[str, int]:
    """
    Aggregate error messages by occurrence count.

    Args:
        entries: List of parsed log entries

    Returns:
        Dictionary mapping error messages to occurrence counts
    """
    error_counts: Dict[str, int] = {}
    for entry in entries:
        if entry.level == "ERROR":
            error_counts[entry.message] = error_counts.get(entry.message, 0) + 1
    return error_counts


def aggregate_api_metrics(entries: List[LogEntry]) -> Dict[str, List[int]]:
    """
    Aggregate API call durations by endpoint.

    Args:
        entries: List of parsed log entries

    Returns:
        Dictionary mapping endpoints to lists of duration values
    """
    endpoint_durations: Dict[str, List[int]] = {}
    for entry in entries:
        if entry.endpoint and entry.duration_ms is not None:
            endpoint_durations.setdefault(entry.endpoint, []).append(entry.duration_ms)
    return endpoint_durations


def track_active_sessions(entries: List[LogEntry]) -> Dict[str, datetime]:
    """
    Track active user sessions based on login/logout events.

    Args:
        entries: List of parsed log entries

    Returns:
        Dictionary mapping user IDs to their login timestamps
    """
    sessions: Dict[str, datetime] = {}
    for entry in entries:
        if entry.user_id and entry.action:
            if "logged in" in entry.action:
                sessions[entry.user_id] = entry.timestamp
            elif "logged out" in entry.action and entry.user_id in sessions:
                del sessions[entry.user_id]
    return sessions


def calculate_api_stats(endpoint_durations: Dict[str, List[int]]) -> List[ApiMetrics]:
    """
    Calculate average latency statistics for each endpoint.

    Args:
        endpoint_durations: Dictionary mapping endpoints to duration lists

    Returns:
        List of ApiMetrics with average latency
    """
    stats = []
    for endpoint, durations in endpoint_durations.items():
        avg_ms = sum(durations) / len(durations)
        stats.append(ApiMetrics(
            endpoint=endpoint,
            avg_ms=avg_ms,
            call_count=len(durations)
        ))
    return stats


def initialize_database(conn: sqlite3.Connection) -> None:
    """
    Create database tables if they don't exist.

    Args:
        conn: SQLite database connection
    """
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS errors (
            dt TEXT,
            message TEXT,
            count INTEGER
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS api_metrics (
            dt TEXT,
            endpoint TEXT,
            avg_ms REAL
        )
    """)


def store_error_stats(
    conn: sqlite3.Connection,
    error_counts: Dict[str, int]
) -> None:
    """
    Store aggregated error statistics in the database.

    Uses parameterized queries to prevent SQL injection.

    Args:
        conn: SQLite database connection
        error_counts: Dictionary of error messages and counts
    """
    cursor = conn.cursor()
    timestamp = datetime.now().isoformat()

    for message, count in error_counts.items():
        cursor.execute(
            "INSERT INTO errors (dt, message, count) VALUES (?, ?, ?)",
            (timestamp, message, count)
        )


def store_api_metrics(
    conn: sqlite3.Connection,
    api_stats: List[ApiMetrics]
) -> None:
    """
    Store API performance metrics in the database.

    Uses parameterized queries to prevent SQL injection.

    Args:
        conn: SQLite database connection
        api_stats: List of API metrics to store
    """
    cursor = conn.cursor()
    timestamp = datetime.now().isoformat()

    for metric in api_stats:
        cursor.execute(
            "INSERT INTO api_metrics (dt, endpoint, avg_ms) VALUES (?, ?, ?)",
            (timestamp, metric.endpoint, metric.avg_ms)
        )


def load_to_database(
    error_counts: Dict[str, int],
    api_stats: List[ApiMetrics],
    db_path: str
) -> None:
    """
    Load aggregated metrics into the database.

    Args:
        error_counts: Dictionary of error messages and counts
        api_stats: List of API metrics
        db_path: Path to SQLite database file
    """
    print(f"Connecting to {DB_HOST}:{DB_PORT} as {DB_USER}...")

    conn = sqlite3.connect(db_path)
    try:
        initialize_database(conn)
        store_error_stats(conn, error_counts)
        store_api_metrics(conn, api_stats)
        conn.commit()
    finally:
        conn.close()


def generate_html_report(
    error_counts: Dict[str, int],
    api_stats: List[ApiMetrics],
    active_sessions: Dict[str, datetime],
    output_path: str
) -> None:
    """
    Generate an HTML report with error summary, API latency, and active sessions.

    Args:
        error_counts: Dictionary of error messages and counts
        api_stats: List of API metrics
        active_sessions: Dictionary of active user sessions
        output_path: Path where the HTML report will be written
    """
    html_parts = [
        "<html>\n<head><title>System Report</title></head>\n<body>\n",
        "<h1>Error Summary</h1>\n<ul>\n"
    ]

    for message, count in error_counts.items():
        html_parts.append(
            f"<li><b>{message}</b>: {count} occurrences</li>\n"
        )

    html_parts.append("</ul>\n")
    html_parts.append("<h2>API Latency</h2>\n<table border='1'>\n")
    html_parts.append("<tr><th>Endpoint</th><th>Avg (ms)</th></tr>\n")

    for metric in api_stats:
        html_parts.append(
            f"<tr><td>{metric.endpoint}</td><td>{round(metric.avg_ms, 1)}</td></tr>\n"
        )

    html_parts.append("</table>\n")
    html_parts.append("<h2>Active Sessions</h2>\n")
    html_parts.append(f"<p>{len(active_sessions)} user(s) currently active</p>\n")
    html_parts.append("</body>\n</html>")

    with open(output_path, "w") as f:
        f.write("".join(html_parts))


def create_sample_log_file(log_path: str) -> None:
    """
    Create a sample log file for testing purposes.

    Args:
        log_path: Path where the sample log file will be created
    """
    sample_lines = [
        "2024-01-01 12:00:00 INFO User 42 logged in\n",
        "2024-01-01 12:05:00 ERROR Database timeout\n",
        "2024-01-01 12:05:05 ERROR Database timeout\n",
        "2024-01-01 12:08:00 INFO API /users/profile took 250ms\n",
        "2024-01-01 12:09:00 WARN Memory usage at 87%\n",
        "2024-01-01 12:10:00 INFO User 42 logged out\n"
    ]

    with open(log_path, "w") as f:
        f.writelines(sample_lines)


def main() -> None:
    """
    Main ETL pipeline: Extract → Transform → Load → Report.

    Orchestrates the entire log processing workflow.
    """
    # Create sample log if it doesn't exist
    if not os.path.exists(LOG_FILE):
        create_sample_log_file(LOG_FILE)

    # Extract: Parse log file
    entries = extract_log_data(LOG_FILE)

    # Transform: Aggregate metrics
    error_counts = aggregate_errors(entries)
    endpoint_durations = aggregate_api_metrics(entries)
    active_sessions = track_active_sessions(entries)
    api_stats = calculate_api_stats(endpoint_durations)

    # Load: Store in database
    load_to_database(error_counts, api_stats, DB_PATH)

    # Report: Generate HTML output
    generate_html_report(error_counts, api_stats, active_sessions, REPORT_OUTPUT)

    print(f"Job finished at {datetime.now()}")


if __name__ == "__main__":
    main()