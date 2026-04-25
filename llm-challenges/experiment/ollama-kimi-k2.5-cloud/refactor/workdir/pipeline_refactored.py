#!/usr/bin/env python3
"""
Server log processing pipeline.

Extracts log entries from server logs, transforms the data into
error summaries, API latency metrics, and active session counts,
then loads the results into an SQLite database and generates an HTML report.
"""

import datetime
import os
import re
import sqlite3
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


# =============================================================================
# Configuration (loaded from environment variables)
# =============================================================================

ENV_DEFAULTS = {
    "DB_PATH": "metrics.db",
    "LOG_FILE": "server.log",
    "DB_HOST": "localhost",
    "DB_PORT": "5432",
    "DB_USER": "admin",
    "DB_PASS": "password123",
}


def get_config(key: str) -> str:
    """Load configuration from environment variables with sensible defaults."""
    return os.getenv(key, ENV_DEFAULTS.get(key, ""))


# =============================================================================
# Data Models
# =============================================================================

@dataclass
class LogEntry:
    """Represents a parsed log entry."""
    timestamp: str
    level: str
    message: str


@dataclass
class ErrorRecord:
    """Aggregated error data."""
    message: str
    count: int


@dataclass
class ApiLatencyRecord:
    """Aggregated API latency data."""
    endpoint: str
    avg_ms: float
    samples: list[int]


@dataclass
class SessionState:
    """Tracks active user sessions."""
    user_id: str
    login_time: str


class ParsedData:
    """Container for all extracted and transformed data."""

    def __init__(self) -> None:
        self.errors: dict[str, int] = defaultdict(int)
        self.api_calls: list[dict[str, str | int]] = []
        self.sessions: dict[str, str] = {}  # user_id -> login_time
        self.warnings: list[LogEntry] = []
        self.user_events: list[dict[str, str]] = []


# =============================================================================
# Log Parsing (Extract)
# =============================================================================

# Regex patterns for log line parsing
LOG_LINE_PATTERN = re.compile(
    r"^(?P<date>\d{4}-\d{2}-\d{2}) "
    r"(?P<time>\d{2}:\d{2}:\d{2}) "
    r"(?P<level>\w+) "
    r"(?P<message>.*)$"
)

USER_EVENT_PATTERN = re.compile(
    r"User\s+(?P<user_id>\S+)\s+(?P<action>.+)"
)

API_CALL_PATTERN = re.compile(
    r"API\s+(?P<endpoint>\S+)\s+took\s+(?P<duration>\d+)ms"
)


def parse_log_line(line: str) -> LogEntry | None:
    """
    Parse a single log line into a LogEntry.

    Args:
        line: Raw log line from the server log file.

    Returns:
        LogEntry if parsing succeeds, None otherwise.
    """
    match = LOG_LINE_PATTERN.match(line.strip())
    if not match:
        return None

    timestamp = f"{match.group('date')} {match.group('time')}"
    return LogEntry(
        timestamp=timestamp,
        level=match.group("level"),
        message=match.group("message"),
    )


def extract_logs(log_file_path: str) -> ParsedData:
    """
    Extract and parse log data from the specified file.

    Args:
        log_file_path: Path to the server log file.

    Returns:
        ParsedData containing all extracted and categorized log information.
    """
    data = ParsedData()
    path = Path(log_file_path)

    if not path.exists():
        return data

    with path.open("r", encoding="utf-8") as f:
        for line in f:
            entry = parse_log_line(line)
            if entry is None:
                continue

            if entry.level == "ERROR":
                data.errors[entry.message] += 1

            elif entry.level == "WARN":
                data.warnings.append(entry)

            elif entry.level == "INFO":
                # User session events
                user_match = USER_EVENT_PATTERN.search(entry.message)
                if user_match:
                    user_id = user_match.group("user_id")
                    action = user_match.group("action")

                    if "logged in" in action:
                        data.sessions[user_id] = entry.timestamp
                    elif "logged out" in action and user_id in data.sessions:
                        del data.sessions[user_id]

                    data.user_events.append({
                        "timestamp": entry.timestamp,
                        "user_id": user_id,
                        "action": action,
                    })
                    continue

                # API call events
                api_match = API_CALL_PATTERN.search(entry.message)
                if api_match:
                    data.api_calls.append({
                        "timestamp": entry.timestamp,
                        "endpoint": api_match.group("endpoint"),
                        "ms": int(api_match.group("duration")),
                    })

    return data


# =============================================================================
# Data Transformation
# =============================================================================

def calculate_api_latency(api_calls: list[dict[str, str | int]]) -> dict[str, ApiLatencyRecord]:
    """
    Calculate average latency per API endpoint.

    Args:
        api_calls: List of API call records with 'endpoint' and 'ms' keys.

    Returns:
        Dictionary mapping endpoint to its ApiLatencyRecord.
    """
    endpoint_stats: dict[str, list[int]] = defaultdict(list)

    for call in api_calls:
        endpoint = str(call["endpoint"])
        duration = int(call["ms"])
        endpoint_stats[endpoint].append(duration)

    return {
        endpoint: ApiLatencyRecord(
            endpoint=endpoint,
            avg_ms=sum(times) / len(times),
            samples=times,
        )
        for endpoint, times in endpoint_stats.items()
    }


def transform_data(data: ParsedData) -> tuple[dict[str, int], dict[str, ApiLatencyRecord], int]:
    """
    Transform extracted data into aggregated metrics.

    Args:
        data: ParsedData from the extract phase.

    Returns:
        Tuple of (error_counts, api_latency, active_sessions).
    """
    api_latency = calculate_api_latency(data.api_calls)
    active_sessions = len(data.sessions)

    return dict(data.errors), api_latency, active_sessions


# =============================================================================
# Database Operations (Load)
# =============================================================================

class DatabaseConnection(Protocol):
    """Protocol for database cursor operations."""

    def execute(self, sql: str, parameters: tuple = ()) -> sqlite3.Cursor: ...
    def close(self) -> None: ...


def init_database(db_path: str) -> sqlite3.Connection:
    """
    Initialize the SQLite database with required tables.

    Args:
        db_path: Path to the SQLite database file.

    Returns:
        Database connection.
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS errors (
            dt TEXT NOT NULL,
            message TEXT NOT NULL,
            count INTEGER NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS api_metrics (
            dt TEXT NOT NULL,
            endpoint TEXT NOT NULL,
            avg_ms REAL NOT NULL
        )
    """)

    conn.commit()
    return conn


def save_errors(
    conn: sqlite3.Connection,
    error_counts: dict[str, int],
    timestamp: datetime.datetime,
) -> None:
    """
    Save error metrics to the database using parameterized queries.

    Args:
        conn: SQLite database connection.
        error_counts: Mapping of error messages to occurrence counts.
        timestamp: When the metrics were recorded.
    """
    cursor = conn.cursor()
    ts_str = str(timestamp)

    for message, count in error_counts.items():
        cursor.execute(
            "INSERT INTO errors (dt, message, count) VALUES (?, ?, ?)",
            (ts_str, message, count),
        )


def save_api_metrics(
    conn: sqlite3.Connection,
    api_latency: dict[str, ApiLatencyRecord],
    timestamp: datetime.datetime,
) -> None:
    """
    Save API latency metrics to the database using parameterized queries.

    Args:
        conn: SQLite database connection.
        api_latency: Dictionary of endpoint latency records.
        timestamp: When the metrics were recorded.
    """
    cursor = conn.cursor()
    ts_str = timestamp.isoformat()

    for record in api_latency.values():
        cursor.execute(
            "INSERT INTO api_metrics (dt, endpoint, avg_ms) VALUES (?, ?, ?)",
            (ts_str, record.endpoint, record.avg_ms),
        )


def load_data(
    db_path: str,
    error_counts: dict[str, int],
    api_latency: dict[str, ApiLatencyRecord],
) -> None:
    """
    Load transformed data into the database.

    Args:
        db_path: Path to the SQLite database file.
        error_counts: Aggregated error counts.
        api_latency: Aggregated API latency data.
    """
    now = datetime.datetime.now()
    db_host = get_config("DB_HOST")
    db_port = get_config("DB_PORT")
    db_user = get_config("DB_USER")

    print(f"Connecting to {db_host}:{db_port} as {db_user}...")

    conn = init_database(db_path)
    try:
        save_errors(conn, error_counts, now)
        save_api_metrics(conn, api_latency, now)
        conn.commit()
    finally:
        conn.close()

    print(f"Job finished at {now}")


# =============================================================================
# Report Generation
# =============================================================================

def generate_html_report(
    error_counts: dict[str, int],
    api_latency: dict[str, ApiLatencyRecord],
    active_sessions: int,
    output_path: str = "report.html",
) -> None:
    """
    Generate an HTML report with error summaries, API latency, and active sessions.

    Args:
        error_counts: Mapping of error messages to occurrence counts.
        api_latency: Dictionary of endpoint latency records.
        active_sessions: Number of currently active user sessions.
        output_path: Where to write the HTML report.
    """
    lines = [
        "<html>",
        "<head><title>System Report</title></head>",
        "<body>",
    ]

    lines.append("<h1>Error Summary</h1>")
    lines.append("<ul>")
    for err_msg, count in error_counts.items():
        lines.append(f"<li><b>{err_msg}</b>: {count} occurrences</li>")
    lines.append("</ul>")

    lines.append("<h2>API Latency</h2>")
    lines.append("<table border='1'>")
    lines.append("<tr><th>Endpoint</th><th>Avg (ms)</th></tr>")
    for record in api_latency.values():
        lines.append(f"<tr><td>{record.endpoint}</td><td>{round(record.avg_ms, 1)}</td></tr>")
    lines.append("</table>")

    lines.append("<h2>Active Sessions</h2>")
    lines.append(f"<p>{active_sessions} user(s) currently active</p>")
    lines.append("</body>")
    lines.append("</html>")

    Path(output_path).write_text("\n".join(lines), encoding="utf-8")


# =============================================================================
# Main Pipeline
# =============================================================================

def run_pipeline(
    log_file_path: str | None = None,
    db_path: str | None = None,
    report_path: str = "report.html",
) -> None:
    """
    Execute the full ETL pipeline.

    Args:
        log_file_path: Path to server log file (defaults to env var LOG_FILE).
        db_path: Path to SQLite database (defaults to env var DB_PATH).
        report_path: Path for HTML output (defaults to "report.html").
    """
    # Resolve configuration
    log_file = log_file_path or get_config("LOG_FILE")
    db = db_path or get_config("DB_PATH")

    # Extract
    raw_data = extract_logs(log_file)

    # Transform
    error_counts, api_latency, active_sessions = transform_data(raw_data)

    # Load
    load_data(db, error_counts, api_latency)

    # Generate Report
    generate_html_report(error_counts, api_latency, active_sessions, report_path)


def main() -> None:
    """Entry point with sample data generation for testing."""
    log_file = get_config("LOG_FILE")

    # Create sample log file if it doesn't exist
    if not Path(log_file).exists():
        sample_logs = [
            "2024-01-01 12:00:00 INFO User 42 logged in",
            "2024-01-01 12:05:00 ERROR Database timeout",
            "2024-01-01 12:05:05 ERROR Database timeout",
            "2024-01-01 12:08:00 INFO API /users/profile took 250ms",
            "2024-01-01 12:09:00 WARN Memory usage at 87%",
            "2024-01-01 12:10:00 INFO User 42 logged out",
        ]
        Path(log_file).write_text("\n".join(sample_logs) + "\n", encoding="utf-8")

    run_pipeline()


if __name__ == "__main__":
    main()
