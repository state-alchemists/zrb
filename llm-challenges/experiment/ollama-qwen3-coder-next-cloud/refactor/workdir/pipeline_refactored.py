"""
Pipeline script for processing server logs and generating a system report.

Follows ETL (Extract → Transform → Load) pattern with secure configuration
via environment variables and parameterized SQL queries.
"""

import datetime
import os
import re
import sqlite3
from dataclasses import dataclass
from typing import Any


# ============================================================================
# Configuration (environment variables)
# ============================================================================


@dataclass(frozen=True)
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
        """Create config from environment variables with defaults."""
        return cls(
            db_path=os.environ.get("DB_PATH", "metrics.db"),
            log_file=os.environ.get("LOG_FILE", "server.log"),
            db_host=os.environ.get("DB_HOST", "localhost"),
            db_port=int(os.environ.get("DB_PORT", "5432")),
            db_user=os.environ.get("DB_USER", "admin"),
            db_pass=os.environ.get("DB_PASS", "password123"),
        )


CONFIG = Config.from_env()


# ============================================================================
# Data models (Transform)
# ============================================================================


@dataclass
class ErrorRecord:
    """Represents an error log entry."""

    datetime: str
    message: str


@dataclass
class ApiCallRecord:
    """Represents an API call metrics entry."""

    datetime: str
    endpoint: str
    duration_ms: int


@dataclass
class SessionRecord:
    """Represents a user session event."""

    datetime: str
    user_id: str
    action: str


# ============================================================================
# Extract (Log Parsing)
# ============================================================================


def _parse_log_line(line: str) -> dict[str, Any] | None:
    """
    Parse a single log line using regex for robust field extraction.

    Expected format:
        <date> <time> <level> <message>

    Examples:
        2024-01-01 12:00:00 INFO User 42 logged in
        2024-01-01 12:05:00 ERROR Database timeout
        2024-01-01 12:08:00 INFO API /users/profile took 250ms
        2024-01-01 12:09:00 WARN Memory usage at 87%

    Returns:
        dict with keys: datetime, level, message, or None if parsing fails.
    """
    pattern = r"^(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2}:\d{2})\s+(INFO|WARN|ERROR)\s+(.*)$"
    match = re.match(pattern, line.strip())
    if not match:
        return None

    date, time, level, message = match.groups()
    return {"datetime": f"{date} {time}", "level": level, "message": message}


def _extract_errors(parsed_lines: list[dict[str, Any]]) -> list[ErrorRecord]:
    """Extract error records from parsed log lines."""
    errors = []
    for entry in parsed_lines:
        if entry["level"] == "ERROR":
            errors.append(ErrorRecord(datetime=entry["datetime"], message=entry["message"]))
    return errors


def _extract_sessions(parsed_lines: list[dict[str, Any]]) -> dict[str, str]:
    """
    Extract user sessions by processing login/logout events.

    Returns:
        dict mapping user_id to last login datetime (active sessions).
    """
    sessions: dict[str, str] = {}

    for entry in parsed_lines:
        if entry["level"] != "INFO":
            continue

        user_match = re.search(r"User\s+(\d+)\s+", entry["message"])
        if not user_match:
            continue

        uid = user_match.group(1)

        if "logged in" in entry["message"]:
            sessions[uid] = entry["datetime"]
        elif "logged out" in entry["message"] and uid in sessions:
            del sessions[uid]

    return sessions


def _extract_api_calls(parsed_lines: list[dict[str, Any]]) -> list[ApiCallRecord]:
    """Extract API call metrics from parsed log lines."""
    api_calls = []

    for entry in parsed_lines:
        if entry["level"] != "INFO" or "API" not in entry["message"]:
            continue

        endpoint_match = re.search(r"API\s+\S+", entry["message"])
        duration_match = re.search(r"took\s+(\d+)ms", entry["message"])

        if endpoint_match and duration_match:
            endpoint = endpoint_match.group().split()[1]
            duration_ms = int(duration_match.group(1))
            api_calls.append(ApiCallRecord(
                datetime=entry["datetime"],
                endpoint=endpoint,
                duration_ms=duration_ms
            ))

    return api_calls


def extract_logs() -> tuple[list[ErrorRecord], dict[str, str], list[ApiCallRecord]]:
    """
    Extract data from the log file.

    Returns:
        Tuple of (errors, sessions, api_calls)
    """
    parsed_lines: list[dict[str, Any]] = []

    if not os.path.exists(CONFIG.log_file):
        return [], {}, []

    with open(CONFIG.log_file, "r") as f:
        for line in f:
            if parsed := _parse_log_line(line):
                parsed_lines.append(parsed)

    errors = _extract_errors(parsed_lines)
    sessions = _extract_sessions(parsed_lines)
    api_calls = _extract_api_calls(parsed_lines)

    return errors, sessions, api_calls


# ============================================================================
# Load (Database Operations)
# ============================================================================


def _init_database(conn: sqlite3.Connection) -> None:
    """Initialize database tables if they don't exist."""
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
    conn.commit()


def _insert_errors(conn: sqlite3.Connection, errors: list[ErrorRecord]) -> None:
    """
    Insert error summary data into the database.

    Uses parameterized queries to prevent SQL injection.
    """
    cursor = conn.cursor()
    now = datetime.datetime.now().isoformat()

    error_counts: dict[str, int] = {}
    for err in errors:
        error_counts[err.message] = error_counts.get(err.message, 0) + 1

    for message, count in error_counts.items():
        cursor.execute(
            "INSERT INTO errors (dt, message, count) VALUES (?, ?, ?)",
            (now, message, count)
        )


def _insert_api_metrics(conn: sqlite3.Connection, api_calls: list[ApiCallRecord]) -> None:
    """
    Insert API latency metrics into the database.

    Uses parameterized queries to prevent SQL injection.
    """
    cursor = conn.cursor()
    now = datetime.datetime.now().isoformat()

    endpoint_times: dict[str, list[int]] = {}
    for call in api_calls:
        endpoint_times.setdefault(call.endpoint, []).append(call.duration_ms)

    for endpoint, times in endpoint_times.items():
        avg_ms = sum(times) / len(times)
        cursor.execute(
            "INSERT INTO api_metrics (dt, endpoint, avg_ms) VALUES (?, ?, ?)",
            (now, endpoint, avg_ms)
        )


def load_to_database(errors: list[ErrorRecord], api_calls: list[ApiCallRecord]) -> None:
    """
    Load processed data into the metrics database.

    Follows ETL 'Load' phase with secure database operations.
    """
    conn = sqlite3.connect(CONFIG.db_path)
    try:
        _init_database(conn)
        _insert_errors(conn, errors)
        _insert_api_metrics(conn, api_calls)
        conn.commit()
    finally:
        conn.close()


# ============================================================================
# Report Generation
# ============================================================================


def generate_report(
    errors: list[ErrorRecord],
    sessions: dict[str, str],
    api_calls: list[ApiCallRecord]
) -> str:
    """
    Generate HTML report with error summary, API latency, and active sessions.

    Returns:
        HTML report as a string.
    """
    # Aggregate error counts
    error_counts: dict[str, int] = {}
    for err in errors:
        error_counts[err.message] = error_counts.get(err.message, 0) + 1

    # Aggregate API latencies
    endpoint_times: dict[str, list[int]] = {}
    for call in api_calls:
        endpoint_times.setdefault(call.endpoint, []).append(call.duration_ms)

    # Build HTML
    lines: list[str] = [
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

    for endpoint, times in endpoint_times.items():
        avg = sum(times) / len(times)
        lines.append(f"<tr><td>{endpoint}</td><td>{round(avg, 1)}</td></tr>")

    lines.extend([
        "</table>",
        f"<h2>Active Sessions</h2>",
        f"<p>{len(sessions)} user(s) currently active</p>",
        "</body>",
        "</html>",
    ])

    return "\n".join(lines)


def save_report(report: str, output_path: str = "report.html") -> None:
    """Save the generated report to a file."""
    with open(output_path, "w") as f:
        f.write(report)


# ============================================================================
# Main Pipeline
# ============================================================================


def run_pipeline() -> None:
    """
    Execute the full ETL pipeline: Extract → Load → Report.

    1. Extract data from log files
    2. Load processed data into database
    3. Generate and save HTML report
    """
    print(f"Connecting to {CONFIG.db_host}:{CONFIG.db_port} as {CONFIG.db_user}...")

    errors, sessions, api_calls = extract_logs()
    load_to_database(errors, api_calls)

    report = generate_report(errors, sessions, api_calls)
    save_report(report)

    print(f"Job finished at {datetime.datetime.now().isoformat()}")


if __name__ == "__main__":
    run_pipeline()
