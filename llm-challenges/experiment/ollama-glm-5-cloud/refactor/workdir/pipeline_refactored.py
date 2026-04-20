"""
Server Log Processing Pipeline

Extracts log data, transforms it into metrics, loads to database,
and generates an HTML report.

Configuration via environment variables:
    LOG_FILE_PATH - Path to server log file (default: server.log)
    DB_PATH - Path to SQLite database (default: metrics.db)
    DB_HOST - Database host for logging (default: localhost)
    DB_PORT - Database port for logging (default: 5432)
    DB_USER - Database user for logging (default: admin)
"""

import dataclasses
import datetime
import os
import re
import sqlite3
from typing import Optional


# Configuration loaded from environment with defaults
@dataclasses.dataclass(frozen=True)
class Config:
    """Pipeline configuration from environment variables."""

    log_file_path: str
    db_path: str
    db_host: str
    db_port: int
    db_user: str

    @classmethod
    def from_env(cls) -> "Config":
        """Load configuration from environment variables."""
        return cls(
            log_file_path=os.getenv("LOG_FILE_PATH", "server.log"),
            db_path=os.getenv("DB_PATH", "metrics.db"),
            db_host=os.getenv("DB_HOST", "localhost"),
            db_port=int(os.getenv("DB_PORT", "5432")),
            db_user=os.getenv("DB_USER", "admin"),
        )


# Log entry types
@dataclasses.dataclass
class ErrorEntry:
    """An error log entry."""

    timestamp: str
    message: str


@dataclasses.dataclass
class UserActionEntry:
    """A user action (login/logout) log entry."""

    timestamp: str
    user_id: str
    action: str


@dataclasses.dataclass
class ApiCallEntry:
    """An API call log entry with latency."""

    timestamp: str
    endpoint: str
    latency_ms: int


@dataclasses.dataclass
class WarningEntry:
    """A warning log entry."""

    timestamp: str
    message: str


@dataclasses.dataclass
class LogData:
    """All extracted log data."""

    errors: list[ErrorEntry]
    user_actions: list[UserActionEntry]
    api_calls: list[ApiCallEntry]
    warnings: list[WarningEntry]


# Regex patterns for log parsing
_LOG_PATTERN = re.compile(
    r"^(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) (?P<level>\w+) (?P<content>.+)$"
)
_USER_PATTERN = re.compile(r"User (?P<user_id>\S+) (?P<action>.+)$")
_API_PATTERN = re.compile(r"API (?P<endpoint>\S+) took (?P<latency>\d+)ms$")


def extract_logs(config: Config) -> LogData:
    """
    Extract and parse log entries from the log file.

    Args:
        config: Pipeline configuration.

    Returns:
        Structured log data containing errors, user actions, API calls, and warnings.
    """
    errors: list[ErrorEntry] = []
    user_actions: list[UserActionEntry] = []
    api_calls: list[ApiCallEntry] = []
    warnings: list[WarningEntry] = []

    if not os.path.exists(config.log_file_path):
        return LogData(errors, user_actions, api_calls, warnings)

    with open(config.log_file_path, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            match = _LOG_PATTERN.match(line)
            if not match:
                continue

            timestamp = match.group("timestamp")
            level = match.group("level")
            content = match.group("content")

            if level == "ERROR":
                errors.append(ErrorEntry(timestamp=timestamp, message=content))

            elif level == "WARN":
                warnings.append(WarningEntry(timestamp=timestamp, message=content))

            elif level == "INFO":
                user_match = _USER_PATTERN.match(content)
                if user_match:
                    user_actions.append(
                        UserActionEntry(
                            timestamp=timestamp,
                            user_id=user_match.group("user_id"),
                            action=user_match.group("action").strip(),
                        )
                    )
                    continue

                api_match = _API_PATTERN.match(content)
                if api_match:
                    api_calls.append(
                        ApiCallEntry(
                            timestamp=timestamp,
                            endpoint=api_match.group("endpoint"),
                            latency_ms=int(api_match.group("latency")),
                        )
                    )

    return LogData(errors, user_actions, api_calls, warnings)


@dataclasses.dataclass
class TransformedMetrics:
    """Transformed metrics ready for database loading."""

    error_counts: dict[str, int]  # message -> count
    api_latency: dict[str, list[int]]  # endpoint -> list of latencies
    active_session_count: int


def transform_data(log_data: LogData) -> TransformedMetrics:
    """
    Transform raw log data into aggregated metrics.

    Args:
        log_data: Extracted log entries.

    Returns:
        Aggregated metrics including error counts, API latencies, and active sessions.
    """
    # Count errors by message
    error_counts: dict[str, int] = {}
    for error in log_data.errors:
        error_counts[error.message] = error_counts.get(error.message, 0) + 1

    # Group API latencies by endpoint
    api_latency: dict[str, list[int]] = {}
    for call in log_data.api_calls:
        if call.endpoint not in api_latency:
            api_latency[call.endpoint] = []
        api_latency[call.endpoint].append(call.latency_ms)

    # Track active sessions
    active_sessions: dict[str, str] = {}  # user_id -> login timestamp
    for action in log_data.user_actions:
        if action.action == "logged in":
            active_sessions[action.user_id] = action.timestamp
        elif action.action == "logged out" and action.user_id in active_sessions:
            del active_sessions[action.user_id]

    return TransformedMetrics(
        error_counts=error_counts,
        api_latency=api_latency,
        active_session_count=len(active_sessions),
    )


def load_to_db(config: Config, metrics: TransformedMetrics) -> None:
    """
    Load transformed metrics into the database.

    Uses parameterized queries to prevent SQL injection.

    Args:
        config: Pipeline configuration.
        metrics: Transformed metrics to persist.
    """
    print(f"Connecting to {config.db_host}:{config.db_port} as {config.db_user}...")

    conn = sqlite3.connect(config.db_path)
    cursor = conn.cursor()

    # Create tables if they don't exist
    cursor.execute(
        "CREATE TABLE IF NOT EXISTS errors (dt TEXT, message TEXT, count INTEGER)"
    )
    cursor.execute(
        "CREATE TABLE IF NOT EXISTS api_metrics (dt TEXT, endpoint TEXT, avg_ms REAL)"
    )

    now = datetime.datetime.now().isoformat()

    # Insert error counts using parameterized queries
    for message, count in metrics.error_counts.items():
        cursor.execute(
            "INSERT INTO errors (dt, message, count) VALUES (?, ?, ?)",
            (now, message, count),
        )

    # Insert API metrics using parameterized queries
    for endpoint, latencies in metrics.api_latency.items():
        avg_latency = sum(latencies) / len(latencies)
        cursor.execute(
            "INSERT INTO api_metrics (dt, endpoint, avg_ms) VALUES (?, ?, ?)",
            (now, endpoint, avg_latency),
        )

    conn.commit()
    conn.close()


def generate_report(metrics: TransformedMetrics, output_path: str = "report.html") -> None:
    """
    Generate an HTML report from transformed metrics.

    Args:
        metrics: Transformed metrics to report.
        output_path: Path to write the HTML report.
    """
    lines = [
        "<html>",
        "<head><title>System Report</title></head>",
        "<body>",
        "<h1>Error Summary</h1>",
        "<ul>",
    ]

    for message, count in metrics.error_counts.items():
        lines.append(f"<li><b>{_escape_html(message)}</b>: {count} occurrences</li>")

    lines.extend([
        "</ul>",
        "<h2>API Latency</h2>",
        "<table border='1'>",
        "<tr><th>Endpoint</th><th>Avg (ms)</th></tr>",
    ])

    for endpoint, latencies in metrics.api_latency.items():
        avg = sum(latencies) / len(latencies)
        lines.append(f"<tr><td>{_escape_html(endpoint)}</td><td>{round(avg, 1)}</td></tr>")

    lines.extend([
        "</table>",
        "<h2>Active Sessions</h2>",
        f"<p>{metrics.active_session_count} user(s) currently active</p>",
        "</body>",
        "</html>",
    ])

    with open(output_path, "w") as f:
        f.write("\n".join(lines))


def _escape_html(text: str) -> str:
    """Escape HTML special characters to prevent XSS."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


def create_sample_log_file(path: str) -> None:
    """
    Create a sample log file for testing.

    Args:
        path: Path to write the sample log file.
    """
    sample_lines = [
        "2024-01-01 12:00:00 INFO User 42 logged in",
        "2024-01-01 12:05:00 ERROR Database timeout",
        "2024-01-01 12:05:05 ERROR Database timeout",
        "2024-01-01 12:08:00 INFO API /users/profile took 250ms",
        "2024-01-01 12:09:00 WARN Memory usage at 87%",
        "2024-01-01 12:10:00 INFO User 42 logged out",
    ]
    with open(path, "w") as f:
        f.write("\n".join(sample_lines) + "\n")


def run_pipeline() -> None:
    """
    Execute the complete ETL pipeline.

    Extracts logs, transforms to metrics, loads to database, and generates report.
    """
    config = Config.from_env()

    # Ensure log file exists
    if not os.path.exists(config.log_file_path):
        create_sample_log_file(config.log_file_path)

    # ETL pipeline
    log_data = extract_logs(config)
    metrics = transform_data(log_data)
    load_to_db(config, metrics)
    generate_report(metrics)

    print(f"Pipeline completed at {datetime.datetime.now()}")


if __name__ == "__main__":
    run_pipeline()