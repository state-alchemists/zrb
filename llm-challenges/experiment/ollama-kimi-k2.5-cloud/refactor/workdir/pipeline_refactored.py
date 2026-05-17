"""
ETL Pipeline for processing server logs and generating reports.

This module extracts log data from server logs, transforms it into metrics,
loads it into a SQLite database, and generates an HTML report.
"""

import datetime
import os
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Protocol


class Config(Protocol):
    """Protocol for configuration sources."""

    db_path: str
    log_file: str
    db_host: str
    db_port: int
    db_user: str
    db_pass: str


@dataclass(frozen=True)
class LogEntry:
    """Represents a parsed log entry."""

    timestamp: str
    level: str
    message: str


@dataclass(frozen=True)
class UserSession:
    """Represents a user session event."""

    timestamp: str
    user_id: str
    action: str


@dataclass(frozen=True)
class ApiCall:
    """Represents an API call event."""

    timestamp: str
    endpoint: str
    duration_ms: int


class EnvironmentConfig:
    """Configuration loaded from environment variables."""

    def __init__(self) -> None:
        self.db_path: str = os.environ.get("DB_PATH", "metrics.db")
        self.log_file: str = os.environ.get("LOG_FILE", "server.log")
        self.db_host: str = os.environ.get("DB_HOST", "localhost")
        self.db_port: int = int(os.environ.get("DB_PORT", "5432"))
        self.db_user: str = os.environ.get("DB_USER", "admin")
        self.db_pass: str = os.environ.get("DB_PASS", "password123")


# Regex patterns for log parsing
LOG_PATTERN = re.compile(
    r"^(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) "
    r"(?P<level>\w+) "
    r"(?P<message>.+)$"
)

USER_PATTERN = re.compile(
    r"User (?P<user_id>\S+) (?P<action>.+)"
)

API_PATTERN = re.compile(
    r"API (?P<endpoint>\S+) took (?P<duration>\d+)ms"
)


def extract_logs(log_file: str) -> List[str]:
    """
    Extract raw log lines from the log file.

    Args:
        log_file: Path to the log file.

    Returns:
        List of log lines. Returns empty list if file doesn't exist.
    """
    log_path = Path(log_file)
    if not log_path.exists():
        return []

    with open(log_file, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]


def parse_log_line(line: str) -> Optional[LogEntry]:
    """
    Parse a single log line into a LogEntry.

    Args:
        line: Raw log line string.

    Returns:
        LogEntry if parsing succeeds, None otherwise.
    """
    match = LOG_PATTERN.match(line)
    if not match:
        return None

    return LogEntry(
        timestamp=match.group("timestamp"),
        level=match.group("level"),
        message=match.group("message"),
    )


def parse_user_event(entry: LogEntry) -> Optional[UserSession]:
    """
    Parse a log entry as a user session event.

    Args:
        entry: Parsed log entry.

    Returns:
        UserSession if this is a user event, None otherwise.
    """
    if entry.level != "INFO":
        return None

    match = USER_PATTERN.match(entry.message)
    if not match:
        return None

    return UserSession(
        timestamp=entry.timestamp,
        user_id=match.group("user_id"),
        action=match.group("action"),
    )


def parse_api_call(entry: LogEntry) -> Optional[ApiCall]:
    """
    Parse a log entry as an API call event.

    Args:
        entry: Parsed log entry.

    Returns:
        ApiCall if this is an API event, None otherwise.
    """
    if entry.level != "INFO":
        return None

    match = API_PATTERN.match(entry.message)
    if not match:
        return None

    return ApiCall(
        timestamp=entry.timestamp,
        endpoint=match.group("endpoint"),
        duration_ms=int(match.group("duration")),
    )


def transform_logs(log_lines: List[str]) -> tuple[Dict[str, int], Dict[str, List[int]], Dict[str, str]]:
    """
    Transform raw log lines into structured data.

    Args:
        log_lines: List of raw log line strings.

    Returns:
        Tuple containing:
            - Error counts by message
            - API duration lists by endpoint
            - Active sessions (user_id -> login timestamp)
    """
    errors: Dict[str, int] = {}
    api_calls: Dict[str, List[int]] = {}
    sessions: Dict[str, str] = {}

    for line in log_lines:
        entry = parse_log_line(line)
        if not entry:
            continue

        # Process errors
        if entry.level == "ERROR":
            errors[entry.message] = errors.get(entry.message, 0) + 1

        # Process warnings
        elif entry.level == "WARN":
            # Warnings are tracked but not aggregated for report
            pass

        # Process user sessions
        elif entry.level == "INFO":
            user_event = parse_user_event(entry)
            if user_event:
                if "logged in" in user_event.action:
                    sessions[user_event.user_id] = user_event.timestamp
                elif "logged out" in user_event.action and user_event.user_id in sessions:
                    del sessions[user_event.user_id]
                continue

            # Process API calls
            api_call = parse_api_call(entry)
            if api_call:
                endpoint = api_call.endpoint
                if endpoint not in api_calls:
                    api_calls[endpoint] = []
                api_calls[endpoint].append(api_call.duration_ms)

    return errors, api_calls, sessions


def load_to_database(
    db_path: str,
    errors: Dict[str, int],
    api_metrics: Dict[str, List[int]],
    host: str,
    port: int,
    user: str,
    password: str,
) -> None:
    """
    Load transformed data into SQLite database.

    Uses parameterized queries to prevent SQL injection.

    Args:
        db_path: Path to the SQLite database file.
        errors: Error counts by message.
        api_metrics: API duration lists by endpoint.
        host: Database host (for logging).
        port: Database port (for logging).
        user: Database user (for logging).
        password: Database password (for logging).
    """
    print(f"Connecting to {host}:{port} as {user}...")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Create tables if they don't exist
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

    # Insert error data using parameterized queries
    now = datetime.datetime.now().isoformat()
    for msg, count in errors.items():
        cursor.execute(
            "INSERT INTO errors VALUES (?, ?, ?)",
            (now, msg, count),
        )

    # Insert API metrics using parameterized queries
    for endpoint, durations in api_metrics.items():
        avg_ms = sum(durations) / len(durations)
        cursor.execute(
            "INSERT INTO api_metrics VALUES (?, ?, ?)",
            (now, endpoint, avg_ms),
        )

    conn.commit()
    conn.close()


def generate_report(
    errors: Dict[str, int],
    api_metrics: Dict[str, List[int]],
    active_sessions: Dict[str, str],
    output_path: str = "report.html",
) -> None:
    """
    Generate HTML report from transformed data.

    Args:
        errors: Error counts by message.
        api_metrics: API duration lists by endpoint.
        active_sessions: Active user sessions.
        output_path: Path to write the HTML report.
    """
    lines: List[str] = [
        "<html>",
        "<head><title>System Report</title></head>",
        "<body>",
        "<h1>Error Summary</h1>",
        "<ul>",
    ]

    for err_msg, count in errors.items():
        escaped_msg = err_msg.replace("<", "&lt;").replace(">", "&gt;")
        lines.append(f"<li><b>{escaped_msg}</b>: {count} occurrences</li>")

    lines.extend([
        "</ul>",
        "<h2>API Latency</h2>",
        "<table border='1'>",
        "<tr><th>Endpoint</th><th>Avg (ms)</th></tr>",
    ])

    for endpoint, durations in api_metrics.items():
        avg = sum(durations) / len(durations)
        lines.append(f"<tr><td>{endpoint}</td><td>{round(avg, 1)}</td></tr>")

    lines.extend([
        "</table>",
        "<h2>Active Sessions</h2>",
        f"<p>{len(active_sessions)} user(s) currently active</p>",
        "</body>",
        "</html>",
    ])

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def create_sample_log(log_file: str) -> None:
    """
    Create a sample log file if it doesn't exist.

    Args:
        log_file: Path to create the sample log file.
    """
    log_path = Path(log_file)
    if log_path.exists():
        return

    sample_lines = [
        "2024-01-01 12:00:00 INFO User 42 logged in",
        "2024-01-01 12:05:00 ERROR Database timeout",
        "2024-01-01 12:05:05 ERROR Database timeout",
        "2024-01-01 12:08:00 INFO API /users/profile took 250ms",
        "2024-01-01 12:09:00 WARN Memory usage at 87%",
        "2024-01-01 12:10:00 INFO User 42 logged out",
    ]

    with open(log_file, "w", encoding="utf-8") as f:
        f.write("\n".join(sample_lines))


def run_pipeline(config: Optional[Config] = None) -> None:
    """
    Execute the full ETL pipeline.

    Args:
        config: Configuration object. Uses EnvironmentConfig if not provided.
    """
    if config is None:
        config = EnvironmentConfig()

    # Extract
    log_lines = extract_logs(config.log_file)

    # Transform
    errors, api_metrics, active_sessions = transform_logs(log_lines)

    # Load
    load_to_database(
        config.db_path,
        errors,
        api_metrics,
        config.db_host,
        config.db_port,
        config.db_user,
        config.db_pass,
    )

    generate_report(errors, api_metrics, active_sessions)

    print(f"Job finished at {datetime.datetime.now()}")


if __name__ == "__main__":
    cfg = EnvironmentConfig()
    create_sample_log(cfg.log_file)
    run_pipeline(cfg)
