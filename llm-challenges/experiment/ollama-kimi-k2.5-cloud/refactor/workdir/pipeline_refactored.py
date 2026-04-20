"""
Log processing pipeline with ETL architecture.

This module processes server logs to generate metrics reports.
Configuration is read from environment variables.
"""

import datetime
import os
import re
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Configuration (from environment variables)
# ---------------------------------------------------------------------------


class Config:
    """Application configuration loaded from environment variables."""

    DB_PATH: str = os.getenv("DB_PATH", "metrics.db")
    LOG_FILE: str = os.getenv("LOG_FILE", "server.log")
    DB_HOST: str = os.getenv("DB_HOST", "localhost")
    DB_PORT: int = int(os.getenv("DB_PORT", "5432"))
    DB_USER: str = os.getenv("DB_USER", "admin")
    DB_PASS: str = os.getenv("DB_PASS", "")
    REPORT_OUTPUT: str = os.getenv("REPORT_OUTPUT", "report.html")


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------


@dataclass
class LogEntry:
    """Base class for parsed log entries."""

    timestamp: str


@dataclass
class ErrorEntry(LogEntry):
    """Represents an error or warning log entry."""

    level: str  # "ERROR" or "WARN"
    message: str


@dataclass
class UserActionEntry(LogEntry):
    """Represents a user login/logout action."""

    user_id: str
    action: str


@dataclass
class ApiCallEntry(LogEntry):
    """Represents an API call with latency information."""

    endpoint: str
    duration_ms: int


@dataclass
class ProcessedData:
    """Container for all extracted and transformed data."""

    errors: list[ErrorEntry] = field(default_factory=list)
    user_actions: list[UserActionEntry] = field(default_factory=list)
    api_calls: list[ApiCallEntry] = field(default_factory=list)
    active_sessions: dict[str, str] = field(default_factory=dict)
    error_counts: dict[str, int] = field(default_factory=dict)
    api_latency_stats: dict[str, list[int]] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Regular Expression Patterns
# ---------------------------------------------------------------------------


LOG_PATTERN = re.compile(
    r"^(?P<timestamp>\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\s+"
    r"(?P<level>ERROR|INFO|WARN)\s+"
    r"(?P<message>.*)$"
)

USER_ACTION_PATTERN = re.compile(
    r"User\s+(?P<user_id>\S+)\s+(?P<action>.+)"
)

API_CALL_PATTERN = re.compile(
    r"API\s+(?P<endpoint>\S+)\s+took\s+(?P<duration>\d+)ms"
)


# ---------------------------------------------------------------------------
# Extract Phase
# ---------------------------------------------------------------------------


def extract_log_entries(log_file_path: str) -> ProcessedData:
    """
    Parse log file and extract structured entries.

    Args:
        log_file_path: Path to the log file to process.

    Returns:
        ProcessedData container with extracted entries.
    """
    data = ProcessedData()

    if not os.path.exists(log_file_path):
        return data

    with open(log_file_path, "r", encoding="utf-8") as file:
        for line in file:
            entry = _parse_log_line(line.strip())
            if entry:
                _categorize_entry(entry, data)

    return data


def _parse_log_line(line: str) -> Optional[dict]:
    """
    Parse a single log line using regex.

    Args:
        line: A single line from the log file.

    Returns:
        Dict with parsed components if matched, None otherwise.
    """
    match = LOG_PATTERN.match(line)
    if not match:
        return None

    return {
        "timestamp": match.group("timestamp"),
        "level": match.group("level"),
        "message": match.group("message"),
    }


def _categorize_entry(parsed: dict, data: ProcessedData) -> None:
    """
    Categorize a parsed log entry into the appropriate collection.

    Args:
        parsed: Dictionary with timestamp, level, and message.
        data: ProcessedData container to populate.
    """
    timestamp = parsed["timestamp"]
    level = parsed["level"]
    message = parsed["message"]

    if level == "ERROR":
        data.errors.append(ErrorEntry(timestamp=timestamp, level=level, message=message))
    elif level == "WARN":
        data.errors.append(ErrorEntry(timestamp=timestamp, level=level, message=message))
    elif level == "INFO":
        # Check for user action
        user_match = USER_ACTION_PATTERN.match(message)
        if user_match:
            user_id = user_match.group("user_id")
            action = user_match.group("action")
            data.user_actions.append(
                UserActionEntry(timestamp=timestamp, user_id=user_id, action=action)
            )
            return

        # Check for API call
        api_match = API_CALL_PATTERN.match(message)
        if api_match:
            endpoint = api_match.group("endpoint")
            duration = int(api_match.group("duration"))
            data.api_calls.append(
                ApiCallEntry(timestamp=timestamp, endpoint=endpoint, duration_ms=duration)
            )


# ---------------------------------------------------------------------------
# Transform Phase
# ---------------------------------------------------------------------------


def transform_data(data: ProcessedData) -> ProcessedData:
    """
    Transform extracted data into aggregated metrics.

    Processes:
    - Error message counts
    - API latency statistics per endpoint
    - Active session tracking from user actions

    Args:
        data: ProcessedData with extracted entries.

    Returns:
        ProcessedData with transformed/aggregated metrics.
    """
    _calculate_error_counts(data)
    _calculate_api_latency_stats(data)
    _track_active_sessions(data)
    return data


def _calculate_error_counts(data: ProcessedData) -> None:
    """Aggregate error messages into count totals."""
    for error in data.errors:
        data.error_counts[error.message] = data.error_counts.get(error.message, 0) + 1


def _calculate_api_latency_stats(data: ProcessedData) -> None:
    """Group API call latencies by endpoint."""
    for call in data.api_calls:
        if call.endpoint not in data.api_latency_stats:
            data.api_latency_stats[call.endpoint] = []
        data.api_latency_stats[call.endpoint].append(call.duration_ms)


def _track_active_sessions(data: ProcessedData) -> None:
    """Track user sessions based on login/logout events."""
    for action in data.user_actions:
        if "logged in" in action.action:
            data.active_sessions[action.user_id] = action.timestamp
        elif "logged out" in action.action and action.user_id in data.active_sessions:
            del data.active_sessions[action.user_id]


# ---------------------------------------------------------------------------
# Load Phase
# ---------------------------------------------------------------------------


def load_to_database(data: ProcessedData, db_path: str) -> None:
    """
    Load transformed metrics into SQLite database.

    Uses parameterized queries to prevent SQL injection.

    Args:
        data: ProcessedData with transformed metrics.
        db_path: Path to the SQLite database file.
    """
    _ensure_tables_exist(db_path)
    _insert_error_metrics(data, db_path)
    _insert_api_metrics(data, db_path)


def _ensure_tables_exist(db_path: str) -> None:
    """Create required tables if they do not exist."""
    with sqlite3.connect(db_path) as conn:
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
        conn.commit()


def _insert_error_metrics(data: ProcessedData, db_path: str) -> None:
    """Insert aggregated error counts into database."""
    current_time = datetime.datetime.now().isoformat()

    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        for message, count in data.error_counts.items():
            # Parameterized query prevents SQL injection
            cursor.execute(
                "INSERT INTO errors (dt, message, count) VALUES (?, ?, ?)",
                (current_time, message, count),
            )
        conn.commit()


def _insert_api_metrics(data: ProcessedData, db_path: str) -> None:
    """Insert API latency averages into database."""
    current_time = datetime.datetime.now().isoformat()

    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        for endpoint, durations in data.api_latency_stats.items():
            avg_ms = sum(durations) / len(durations)
            # Parameterized query prevents SQL injection
            cursor.execute(
                "INSERT INTO api_metrics (dt, endpoint, avg_ms) VALUES (?, ?, ?)",
                (current_time, endpoint, avg_ms),
            )
        conn.commit()


def generate_report(data: ProcessedData, output_path: str) -> None:
    """
    Generate HTML report from processed data.

    Args:
        data: ProcessedData with transformed metrics.
        output_path: Path where the HTML report will be written.
    """
    html_parts = [
        "<html>",
        "<head><title>System Report</title></head>",
        "<body>",
        _build_error_summary_section(data),
        _build_api_latency_section(data),
        _build_active_sessions_section(data),
        "</body>",
        "</html>",
    ]

    report_html = "\n".join(html_parts)

    with open(output_path, "w", encoding="utf-8") as file:
        file.write(report_html)


def _build_error_summary_section(data: ProcessedData) -> str:
    """Build HTML for error summary section."""
    lines = ["<h1>Error Summary</h1>", "<ul>"]

    for message, count in data.error_counts.items():
        escaped_message = _escape_html(message)
        lines.append(f"<li><b>{escaped_message}</b>: {count} occurrences</li>")

    lines.append("</ul>")
    return "\n".join(lines)


def _build_api_latency_section(data: ProcessedData) -> str:
    """Build HTML for API latency table section."""
    lines = [
        "<h2>API Latency</h2>",
        "<table border='1'>",
        "<tr><th>Endpoint</th><th>Avg (ms)</th></tr>",
    ]

    for endpoint, durations in data.api_latency_stats.items():
        avg = sum(durations) / len(durations)
        escaped_endpoint = _escape_html(endpoint)
        lines.append(
            f"<tr><td>{escaped_endpoint}</td><td>{round(avg, 1)}</td></tr>"
        )

    lines.append("</table>")
    return "\n".join(lines)


def _build_active_sessions_section(data: ProcessedData) -> str:
    """Build HTML for active sessions section."""
    active_count = len(data.active_sessions)
    return f"<h2>Active Sessions</h2>\n<p>{active_count} user(s) currently active</p>"


def _escape_html(text: str) -> str:
    """Escape HTML special characters to prevent XSS."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


# ---------------------------------------------------------------------------
# Main Pipeline
# ---------------------------------------------------------------------------


def run_pipeline(config: Optional[type[Config]] = None) -> None:
    """
    Execute the full ETL pipeline.

    Extracts data from log file, transforms it into metrics,
    loads into database, and generates HTML report.

    Args:
        config: Configuration class. Uses Config by default.
    """
    cfg = config or Config

    print(f"Connecting to {cfg.DB_HOST}:{cfg.DB_PORT} as {cfg.DB_USER}...")

    # Extract
    data = extract_log_entries(cfg.LOG_FILE)

    # Transform
    data = transform_data(data)

    # Load
    load_to_database(data, cfg.DB_PATH)

    # Generate Report
    generate_report(data, cfg.REPORT_OUTPUT)

    print(f"Job finished at {datetime.datetime.now()}")


def create_sample_log(log_file_path: str) -> None:
    """Create a sample log file for testing purposes."""
    sample_lines = [
        "2024-01-01 12:00:00 INFO User 42 logged in\n",
        "2024-01-01 12:05:00 ERROR Database timeout\n",
        "2024-01-01 12:05:05 ERROR Database timeout\n",
        "2024-01-01 12:08:00 INFO API /users/profile took 250ms\n",
        "2024-01-01 12:09:00 WARN Memory usage at 87%\n",
        "2024-01-01 12:10:00 INFO User 42 logged out\n",
    ]

    with open(log_file_path, "w", encoding="utf-8") as file:
        file.writelines(sample_lines)


if __name__ == "__main__":
    # Create sample log if not exists
    if not os.path.exists(Config.LOG_FILE):
        create_sample_log(Config.LOG_FILE)

    run_pipeline()
