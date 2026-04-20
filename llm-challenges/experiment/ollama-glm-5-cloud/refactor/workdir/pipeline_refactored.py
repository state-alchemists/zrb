"""Server log processing pipeline.

This module implements an ETL pipeline that:
1. Extracts log entries from server logs
2. Transforms them into structured metrics
3. Loads results into a database and generates an HTML report

Configuration is loaded from environment variables.
"""

from __future__ import annotations

import datetime
import os
import re
import sqlite3
from dataclasses import dataclass, field
from typing import Optional


# Configuration from environment variables
class Config:
    """Pipeline configuration loaded from environment variables."""

    DB_PATH: str = os.getenv("DB_PATH", "metrics.db")
    LOG_FILE: str = os.getenv("LOG_FILE", "server.log")
    DB_HOST: str = os.getenv("DB_HOST", "localhost")
    DB_PORT: int = int(os.getenv("DB_PORT", "5432"))
    DB_USER: str = os.getenv("DB_USER", "admin")
    DB_PASS: str = os.getenv("DB_PASS", "password123")


# Regex patterns for log parsing
LOG_PATTERN = re.compile(
    r"^(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) "
    r"(?P<level>ERROR|INFO|WARN)\s+"
    r"(?P<message>.+)$"
)

USER_ACTION_PATTERN = re.compile(
    r"User (?P<user_id>\S+) (?P<action>logged in|logged out)"
)

API_CALL_PATTERN = re.compile(
    r"API (?P<endpoint>\S+) took (?P<duration>\d+)ms"
)


@dataclass
class ErrorEntry:
    """Represents an error log entry."""
    timestamp: str
    message: str


@dataclass
class UserSession:
    """Represents a user session event."""
    timestamp: str
    user_id: str
    action: str


@dataclass
class ApiCall:
    """Represents an API call with latency metrics."""
    timestamp: str
    endpoint: str
    duration_ms: int


@dataclass
class LogData:
    """Container for all parsed log data."""
    errors: list[ErrorEntry] = field(default_factory=list)
    user_sessions: list[UserSession] = field(default_factory=list)
    api_calls: list[ApiCall] = field(default_factory=list)
    warnings: list[ErrorEntry] = field(default_factory=list)
    active_sessions: dict[str, str] = field(default_factory=dict)


@dataclass
class ErrorSummary:
    """Aggregated error statistics."""
    message: str
    count: int


@dataclass
class ApiLatency:
    """Aggregated API latency statistics."""
    endpoint: str
    avg_ms: float


@dataclass
class TransformedData:
    """Container for transformed/aggregated metrics."""
    error_summaries: list[ErrorSummary] = field(default_factory=list)
    api_latencies: list[ApiLatency] = field(default_factory=list)
    active_session_count: int = 0
    warnings: list[ErrorEntry] = field(default_factory=list)


# -----------------------------------------------------------------------------
# EXTRACT: Parse log file into structured data
# -----------------------------------------------------------------------------

def parse_log_line(line: str) -> Optional[tuple[str, str, str]]:
    """Parse a single log line using regex.

    Args:
        line: Raw log line string.

    Returns:
        Tuple of (timestamp, level, message) if valid, None otherwise.
    """
    match = LOG_PATTERN.match(line.strip())
    if match:
        return match.group("timestamp"), match.group("level"), match.group("message")
    return None


def parse_user_action(message: str) -> Optional[tuple[str, str]]:
    """Extract user ID and action from a user-related log message.

    Args:
        message: Log message containing user action.

    Returns:
        Tuple of (user_id, action) if found, None otherwise.
    """
    match = USER_ACTION_PATTERN.search(message)
    if match:
        return match.group("user_id"), match.group("action")
    return None


def parse_api_call(message: str) -> Optional[tuple[str, int]]:
    """Extract endpoint and duration from an API log message.

    Args:
        message: Log message containing API call info.

    Returns:
        Tuple of (endpoint, duration_ms) if found, None otherwise.
    """
    match = API_CALL_PATTERN.search(message)
    if match:
        return match.group("endpoint"), int(match.group("duration"))
    return None


def extract_log_data(config: Config) -> LogData:
    """Extract and parse all entries from the log file.

    Args:
        config: Pipeline configuration.

    Returns:
        LogData container with all parsed entries.
    """
    log_data = LogData()

    if not os.path.exists(config.LOG_FILE):
        return log_data

    with open(config.LOG_FILE, "r") as f:
        for line in f:
            parsed = parse_log_line(line)
            if not parsed:
                continue

            timestamp, level, message = parsed

            if level == "ERROR":
                log_data.errors.append(ErrorEntry(timestamp=timestamp, message=message))

            elif level == "WARN":
                log_data.warnings.append(ErrorEntry(timestamp=timestamp, message=message))

            elif level == "INFO":
                if "User" in message:
                    user_info = parse_user_action(message)
                    if user_info:
                        user_id, action = user_info
                        log_data.user_sessions.append(
                            UserSession(timestamp=timestamp, user_id=user_id, action=action)
                        )
                        # Track active sessions
                        if action == "logged in":
                            log_data.active_sessions[user_id] = timestamp
                        elif action == "logged out" and user_id in log_data.active_sessions:
                            log_data.active_sessions.pop(user_id)

                elif "API" in message:
                    api_info = parse_api_call(message)
                    if api_info:
                        endpoint, duration = api_info
                        log_data.api_calls.append(
                            ApiCall(timestamp=timestamp, endpoint=endpoint, duration_ms=duration)
                        )

    return log_data


# -----------------------------------------------------------------------------
# TRANSFORM: Aggregate and process extracted data
# -----------------------------------------------------------------------------

def aggregate_errors(errors: list[ErrorEntry]) -> list[ErrorSummary]:
    """Aggregate error counts by message.

    Args:
        errors: List of error entries.

    Returns:
        List of error summaries with counts.
    """
    counts: dict[str, int] = {}
    for error in errors:
        counts[error.message] = counts.get(error.message, 0) + 1

    return [ErrorSummary(message=msg, count=count) for msg, count in counts.items()]


def aggregate_api_latency(api_calls: list[ApiCall]) -> list[ApiLatency]:
    """Calculate average latency per API endpoint.

    Args:
        api_calls: List of API call entries.

    Returns:
        List of API latency summaries with average durations.
    """
    endpoint_times: dict[str, list[int]] = {}
    for call in api_calls:
        endpoint_times.setdefault(call.endpoint, []).append(call.duration_ms)

    return [
        ApiLatency(endpoint=ep, avg_ms=sum(times) / len(times))
        for ep, times in endpoint_times.items()
    ]


def transform_data(log_data: LogData) -> TransformedData:
    """Transform raw log data into aggregated metrics.

    Args:
        log_data: Container with parsed log entries.

    Returns:
        TransformedData with aggregated statistics.
    """
    return TransformedData(
        error_summaries=aggregate_errors(log_data.errors),
        api_latencies=aggregate_api_latency(log_data.api_calls),
        active_session_count=len(log_data.active_sessions),
        warnings=log_data.warnings,
    )


# -----------------------------------------------------------------------------
# LOAD: Write to database and generate report
# -----------------------------------------------------------------------------

def init_database(conn: sqlite3.Connection) -> None:
    """Initialize database tables if they don't exist.

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
    conn.commit()


def load_errors(conn: sqlite3.Connection, summaries: list[ErrorSummary]) -> None:
    """Insert error summaries into the database using parameterized queries.

    Args:
        conn: SQLite database connection.
        summaries: List of error summaries to insert.
    """
    cursor = conn.cursor()
    timestamp = datetime.datetime.now().isoformat()

    for summary in summaries:
        cursor.execute(
            "INSERT INTO errors (dt, message, count) VALUES (?, ?, ?)",
            (timestamp, summary.message, summary.count)
        )
    conn.commit()


def load_api_metrics(conn: sqlite3.Connection, latencies: list[ApiLatency]) -> None:
    """Insert API latency metrics into the database using parameterized queries.

    Args:
        conn: SQLite database connection.
        latencies: List of API latency summaries to insert.
    """
    cursor = conn.cursor()
    timestamp = datetime.datetime.now().isoformat()

    for latency in latencies:
        cursor.execute(
            "INSERT INTO api_metrics (dt, endpoint, avg_ms) VALUES (?, ?, ?)",
            (timestamp, latency.endpoint, latency.avg_ms)
        )
    conn.commit()


def generate_report(data: TransformedData, output_path: str = "report.html") -> None:
    """Generate HTML report from transformed data.

    Args:
        data: Transformed metrics data.
        output_path: Path to write the HTML report.
    """
    lines = [
        "<html>",
        "<head><title>System Report</title></head>",
        "<body>",
        "<h1>Error Summary</h1>",
        "<ul>",
    ]

    for summary in data.error_summaries:
        lines.append(f"<li><b>{summary.message}</b>: {summary.count} occurrences</li>")

    lines.extend([
        "</ul>",
        "<h2>API Latency</h2>",
        "<table border='1'>",
        "<tr><th>Endpoint</th><th>Avg (ms)</th></tr>",
    ])

    for latency in data.api_latencies:
        lines.append(f"<tr><td>{latency.endpoint}</td><td>{round(latency.avg_ms, 1)}</td></tr>")

    lines.extend([
        "</table>",
        "<h2>Active Sessions</h2>",
        f"<p>{data.active_session_count} user(s) currently active</p>",
        "</body>",
        "</html>",
    ])

    with open(output_path, "w") as f:
        f.write("\n".join(lines))


def load_data(transformed: TransformedData, config: Config) -> None:
    """Load transformed data into database and generate report.

    Args:
        transformed: Aggregated metrics data.
        config: Pipeline configuration.
    """
    print(f"Connecting to {config.DB_HOST}:{config.DB_PORT} as {config.DB_USER}...")

    conn = sqlite3.connect(config.DB_PATH)
    try:
        init_database(conn)
        load_errors(conn, transformed.error_summaries)
        load_api_metrics(conn, transformed.api_latencies)
    finally:
        conn.close()

    generate_report(transformed)
    print(f"Job finished at {datetime.datetime.now()}")


# -----------------------------------------------------------------------------
# MAIN: Run the pipeline
# -----------------------------------------------------------------------------

def create_sample_log_file(path: str) -> None:
    """Create a sample log file for testing.

    Args:
        path: Path to write the sample log file.
    """
    sample_logs = [
        "2024-01-01 12:00:00 INFO User 42 logged in",
        "2024-01-01 12:05:00 ERROR Database timeout",
        "2024-01-01 12:05:05 ERROR Database timeout",
        "2024-01-01 12:08:00 INFO API /users/profile took 250ms",
        "2024-01-01 12:09:00 WARN Memory usage at 87%",
        "2024-01-01 12:10:00 INFO User 42 logged out",
    ]
    with open(path, "w") as f:
        f.write("\n".join(sample_logs) + "\n")


def run_pipeline(config: Optional[Config] = None) -> None:
    """Execute the full ETL pipeline.

    Args:
        config: Optional configuration override. Uses environment defaults if not provided.
    """
    if config is None:
        config = Config()

    # Ensure log file exists for demo
    if not os.path.exists(config.LOG_FILE):
        create_sample_log_file(config.LOG_FILE)

    # ETL pipeline
    log_data = extract_log_data(config)
    transformed = transform_data(log_data)
    load_data(transformed, config)


if __name__ == "__main__":
    run_pipeline()