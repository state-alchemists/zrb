"""
Pipeline refactored: Extracts log data, transforms it, and loads into a database.

Configuration via environment variables:
    LOG_FILE: Path to server log file (default: server.log)
    DB_PATH: Path to SQLite database file (default: metrics.db)

Author: Refactored for security and maintainability
"""

import datetime
import os
import re
import sqlite3
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any


# Configuration via environment variables with defaults
DB_PATH = os.environ.get("DB_PATH", "metrics.db")
LOG_FILE = os.environ.get("LOG_FILE", "server.log")


class LogLevel(Enum):
    """Log message severity levels."""
    ERROR = "ERROR"
    INFO = "INFO"
    WARN = "WARN"


@dataclass
class LogEntry:
    """Represents a parsed log line."""
    timestamp: datetime.datetime
    level: LogLevel
    message: str


@dataclass
class ErrorEntry:
    """Error log entry for database storage."""
    dt: datetime.datetime
    message: str
    count: int


@dataclass
class ApiMetric:
    """API latency metric for database storage."""
    dt: datetime.datetime
    endpoint: str
    avg_ms: float


def get_log_file_path() -> Path:
    """Return the log file path from environment or default."""
    return Path(LOG_FILE)


def get_db_path() -> Path:
    """Return the database path from environment or default."""
    return Path(DB_PATH)


def parse_log_line(line: str) -> LogEntry | None:
    """
    Parse a single log line using regex.

    Expected format: YYYY-MM-DD HH:MM:SS LEVEL Message

    Returns None if the line doesn't match the expected format.
    """
    pattern = r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) (ERROR|INFO|WARN) (.*)$"
    match = re.match(pattern, line)
    if not match:
        return None

    timestamp_str, level_str, message = match.groups()
    return LogEntry(
        timestamp=datetime.datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S"),
        level=LogLevel(level_str),
        message=message,
    )


def extract_logs(log_path: Path) -> list[LogEntry]:
    """
    Extract and parse all valid log entries from a file.

    Args:
        log_path: Path to the log file.

    Returns:
        List of parsed LogEntry objects.
    """
    entries = []
    if not log_path.exists():
        return entries

    with open(log_path, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            entry = parse_log_line(line)
            if entry:
                entries.append(entry)

    return entries


def transform_data(entries: list[LogEntry]) -> tuple[dict[str, int], dict[str, Any], dict[str, float]]:
    """
    Transform raw log entries into aggregated data structures.

    Args:
        entries: List of parsed log entries.

    Returns:
        Tuple of (error_counts, sessions_by_user, api_latencies_by_endpoint)
    """
    error_counts: dict[str, int] = {}
    sessions_by_user: dict[str, str] = {}
    api_latencies_by_endpoint: dict[str, list[float]] = {}

    for entry in entries:
        if entry.level == LogLevel.ERROR:
            msg = entry.message
            error_counts[msg] = error_counts.get(msg, 0) + 1

        elif entry.level == LogLevel.INFO:
            # Parse User events
            user_match = re.search(r"User (\d+) (.+)", entry.message)
            if user_match:
                user_id, action = user_match.groups()
                if "logged in" in action:
                    sessions_by_user[user_id] = entry.timestamp.isoformat()
                elif "logged out" in action and user_id in sessions_by_user:
                    del sessions_by_user[user_id]

            # Parse API latency events
            api_match = re.search(r"API (\S+) took (\d+)ms", entry.message)
            if api_match:
                endpoint, latency_ms = api_match.groups()
                api_latencies_by_endpoint.setdefault(endpoint, []).append(float(latency_ms))

    return error_counts, sessions_by_user, api_latencies_by_endpoint


def load_to_database(
    db_path: Path,
    error_counts: dict[str, int],
    api_latencies_by_endpoint: dict[str, list[float]],
) -> None:
    """
    Load transformed data into SQLite database using parameterized queries.

    Args:
        db_path: Path to the SQLite database file.
        error_counts: Dictionary of error message -> count.
        api_latencies_by_endpoint: Dictionary of endpoint -> list of latencies.
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute(
        "CREATE TABLE IF NOT EXISTS errors (dt TEXT, message TEXT, count INTEGER)"
    )
    cursor.execute(
        "CREATE TABLE IF NOT EXISTS api_metrics (dt TEXT, endpoint TEXT, avg_ms REAL)"
    )

    now = datetime.datetime.now()

    # Parameterized query for errors (no SQL injection)
    for msg, count in error_counts.items():
        cursor.execute(
            "INSERT INTO errors (dt, message, count) VALUES (?, ?, ?)",
            (now.isoformat(), msg, count),
        )

    # Compute and store API latency metrics using parameterized queries
    for endpoint, latencies in api_latencies_by_endpoint.items():
        avg_ms = sum(latencies) / len(latencies)
        cursor.execute(
            "INSERT INTO api_metrics (dt, endpoint, avg_ms) VALUES (?, ?, ?)",
            (now.isoformat(), endpoint, avg_ms),
        )

    conn.commit()
    conn.close()


def generate_report(
    error_counts: dict[str, int],
    api_latencies_by_endpoint: dict[str, list[float]],
    sessions_by_user: dict[str, str],
) -> str:
    """
    Generate HTML report content.

    Args:
        error_counts: Dictionary of error message -> count.
        api_latencies_by_endpoint: Dictionary of endpoint -> list of latencies.
        sessions_by_user: Dictionary of user_id -> session_start_time.

    Returns:
        HTML string report.
    """
    html_parts = [
        "<html>",
        "<head><title>System Report</title></head>",
        "<body>",
    ]

    # Error Summary
    html_parts.append("<h1>Error Summary</h1>")
    html_parts.append("<ul>")
    for err_msg, count in error_counts.items():
        html_parts.append(f"<li><b>{err_msg}</b>: {count} occurrences</li>")
    html_parts.append("</ul>")

    # API Latency
    html_parts.append("<h2>API Latency</h2>")
    html_parts.append("<table border='1'>")
    html_parts.append("<tr><th>Endpoint</th><th>Avg (ms)</th></tr>")
    for endpoint, latencies in api_latencies_by_endpoint.items():
        avg = sum(latencies) / len(latencies)
        html_parts.append(f"<tr><td>{endpoint}</td><td>{round(avg, 1)}</td></tr>")
    html_parts.append("</table>")

    # Active Sessions
    html_parts.append("<h2>Active Sessions</h2>")
    html_parts.append(f"<p>{len(sessions_by_user)} user(s) currently active</p>")

    html_parts.append("</body>")
    html_parts.append("</html>")

    return "\n".join(html_parts)


def save_report(report_html: str, output_path: Path) -> None:
    """
    Save the generated report to a file.

    Args:
        report_html: HTML content of the report.
        output_path: Path to save the report file.
    """
    with open(output_path, "w") as f:
        f.write(report_html)


def main() -> None:
    """Main entry point for the pipeline: Extract -> Transform -> Load."""
    log_path = get_log_file_path()
    db_path = get_db_path()
    output_path = Path("report.html")

    # Extract phase
    entries = extract_logs(log_path)

    # Transform phase
    error_counts, sessions_by_user, api_latencies_by_endpoint = transform_data(entries)

    # Load phase
    load_to_database(db_path, error_counts, api_latencies_by_endpoint)

    # Generate and save report
    report_html = generate_report(error_counts, api_latencies_by_endpoint, sessions_by_user)
    save_report(report_html, output_path)

    print(f"Job finished at {datetime.datetime.now()}")


if __name__ == "__main__":
    # Create sample log file if it doesn't exist (for testing)
    log_path = get_log_file_path()
    if not log_path.exists():
        log_path.write_text(
            "2024-01-01 12:00:00 INFO User 42 logged in\n"
            "2024-01-01 12:05:00 ERROR Database timeout\n"
            "2024-01-01 12:05:05 ERROR Database timeout\n"
            "2024-01-01 12:08:00 INFO API /users/profile took 250ms\n"
            "2024-01-01 12:09:00 WARN Memory usage at 87%\n"
            "2024-01-01 12:10:00 INFO User 42 logged out\n"
        )

    main()
