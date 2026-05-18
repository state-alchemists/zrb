"""
Log processing pipeline – Extract, Transform, Load (ETL).

Processes server logs to generate metrics reports with error summaries,
API latency statistics, and active session counts.

Configuration via environment variables:
    LOG_FILE_PATH    – Path to server log file (default: server.log)
    DB_PATH          – Path to SQLite database (default: metrics.db)
"""

import dataclasses
import datetime
import os
import re
import sqlite3
from collections import defaultdict
from typing import Optional


@dataclasses.dataclass
class Config:
    """Runtime configuration loaded from environment variables."""

    log_file_path: str
    db_path: str

    @classmethod
    def from_env(cls) -> "Config":
        """Load configuration from environment with sensible defaults."""
        return cls(
            log_file_path=os.getenv("LOG_FILE_PATH", "server.log"),
            db_path=os.getenv("DB_PATH", "metrics.db"),
        )


@dataclasses.dataclass
class ErrorEntry:
    """Represents an error log entry."""

    timestamp: str
    message: str


@dataclasses.dataclass
class UserAction:
    """Represents a user session action (login/logout)."""

    timestamp: str
    user_id: str
    action: str


@dataclasses.dataclass
class ApiCall:
    """Represents an API call with latency measurement."""

    timestamp: str
    endpoint: str
    latency_ms: int


@dataclasses.dataclass
class WarningEntry:
    """Represents a warning log entry."""

    timestamp: str
    message: str


@dataclasses.dataclass
class ParsedLogData:
    """Aggregated results from log parsing."""

    errors: list[ErrorEntry]
    user_actions: list[UserAction]
    api_calls: list[ApiCall]
    warnings: list[WarningEntry]


# Regex patterns for robust log line parsing
_LOG_PATTERN = re.compile(
    r"^(?P<timestamp>\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\s+"
    r"(?P<level>INFO|ERROR|WARN)\s+"
    r"(?P<content>.*)$"
)

_USER_ACTION_PATTERN = re.compile(
    r"^User\s+(?P<user_id>\S+)\s+(?P<action>.+)$"
)

_API_CALL_PATTERN = re.compile(
    r"^API\s+(?P<endpoint>\S+)(?:\s+took\s+(?P<latency>\d+)ms)?$"
)


def extract(log_path: str) -> list[str]:
    """
    Extract log lines from file.

    Args:
        log_path: Path to the log file.

    Returns:
        List of raw log lines.

    Raises:
        FileNotFoundError: If log file does not exist.
    """
    if not os.path.exists(log_path):
        raise FileNotFoundError(f"Log file not found: {log_path}")

    with open(log_path, "r", encoding="utf-8") as f:
        return f.readlines()


def _parse_log_line(line: str) -> Optional[tuple[str, str, str]]:
    """
    Parse a single log line into timestamp, level, and content.

    Args:
        line: Raw log line.

    Returns:
        Tuple of (timestamp, level, content) or None if line doesn't match.
    """
    match = _LOG_PATTERN.match(line.strip())
    if not match:
        return None
    return match.group("timestamp"), match.group("level"), match.group("content")


def _parse_user_action(content: str, timestamp: str) -> Optional[UserAction]:
    """Parse user login/logout action from log content."""
    match = _USER_ACTION_PATTERN.match(content)
    if not match:
        return None
    return UserAction(
        timestamp=timestamp,
        user_id=match.group("user_id"),
        action=match.group("action").strip(),
    )


def _parse_api_call(content: str, timestamp: str) -> Optional[ApiCall]:
    """Parse API call with latency from log content."""
    match = _API_CALL_PATTERN.match(content)
    if not match:
        return None
    latency_str = match.group("latency") or "0"
    return ApiCall(
        timestamp=timestamp,
        endpoint=match.group("endpoint"),
        latency_ms=int(latency_str),
    )


def transform(log_lines: list[str]) -> ParsedLogData:
    """
    Transform raw log lines into structured data.

    Args:
        log_lines: Raw log lines from extract phase.

    Returns:
        ParsedLogData with categorized entries.
    """
    errors: list[ErrorEntry] = []
    user_actions: list[UserAction] = []
    api_calls: list[ApiCall] = []
    warnings: list[WarningEntry] = []

    for line in log_lines:
        parsed = _parse_log_line(line)
        if not parsed:
            continue

        timestamp, level, content = parsed

        if level == "ERROR":
            errors.append(ErrorEntry(timestamp=timestamp, message=content))
        elif level == "WARN":
            warnings.append(WarningEntry(timestamp=timestamp, message=content))
        elif level == "INFO":
            if content.startswith("User "):
                action = _parse_user_action(content, timestamp)
                if action:
                    user_actions.append(action)
            elif content.startswith("API "):
                call = _parse_api_call(content, timestamp)
                if call:
                    api_calls.append(call)

    return ParsedLogData(
        errors=errors,
        user_actions=user_actions,
        api_calls=api_calls,
        warnings=warnings,
    )


def _count_errors(errors: list[ErrorEntry]) -> dict[str, int]:
    """Aggregate error counts by message."""
    counts: dict[str, int] = defaultdict(int)
    for error in errors:
        counts[error.message] += 1
    return dict(counts)


def _compute_api_stats(api_calls: list[ApiCall]) -> dict[str, float]:
    """Compute average latency per endpoint."""
    latency_by_endpoint: dict[str, list[int]] = defaultdict(list)
    for call in api_calls:
        latency_by_endpoint[call.endpoint].append(call.latency_ms)

    stats: dict[str, float] = {}
    for endpoint, latencies in latency_by_endpoint.items():
        stats[endpoint] = sum(latencies) / len(latencies)
    return stats


def _count_active_sessions(user_actions: list[UserAction]) -> set[str]:
    """
    Count currently active sessions.

    A session is active if user logged in without a subsequent logout.
    """
    sessions: set[str] = set()
    for action in user_actions:
        if "logged in" in action.action:
            sessions.add(action.user_id)
        elif "logged out" in action.action:
            sessions.discard(action.user_id)
    return sessions


def load(
    db_path: str,
    error_counts: dict[str, int],
    api_stats: dict[str, float],
) -> None:
    """
    Load aggregated metrics into database.

    Uses parameterized queries to prevent SQL injection.

    Args:
        db_path: Path to SQLite database.
        error_counts: Error message to count mapping.
        api_stats: Endpoint to average latency mapping.
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute(
        "CREATE TABLE IF NOT EXISTS errors "
        "(dt TEXT, message TEXT, count INTEGER)"
    )
    cursor.execute(
        "CREATE TABLE IF NOT EXISTS api_metrics "
        "(dt TEXT, endpoint TEXT, avg_ms REAL)"
    )

    timestamp = datetime.datetime.now().isoformat()

    for message, count in error_counts.items():
        cursor.execute(
            "INSERT INTO errors (dt, message, count) VALUES (?, ?, ?)",
            (timestamp, message, count),
        )

    for endpoint, avg_latency in api_stats.items():
        cursor.execute(
            "INSERT INTO api_metrics (dt, endpoint, avg_ms) VALUES (?, ?, ?)",
            (timestamp, endpoint, avg_latency),
        )

    conn.commit()
    conn.close()


def generate_report(
    error_counts: dict[str, int],
    api_stats: dict[str, float],
    active_sessions: int,
    output_path: str = "report.html",
) -> None:
    """
    Generate HTML report with metrics.

    Args:
        error_counts: Error message to count mapping.
        api_stats: Endpoint to average latency mapping.
        active_sessions: Number of active user sessions.
        output_path: Path for output HTML file.
    """
    lines = [
        "<!DOCTYPE html>",
        "<html>",
        "<head><title>System Report</title></head>",
        "<body>",
        "<h1>Error Summary</h1>",
        "<ul>",
    ]

    for message, count in sorted(error_counts.items()):
        lines.append(f"<li><b>{message}</b>: {count} occurrences</li>")

    lines.extend([
        "</ul>",
        "<h2>API Latency</h2>",
        "<table border='1'>",
        "<tr><th>Endpoint</th><th>Avg (ms)</th></tr>",
    ])

    for endpoint, avg_latency in sorted(api_stats.items()):
        lines.append(
            f"<tr><td>{endpoint}</td><td>{avg_latency:.1f}</td></tr>"
        )

    lines.extend([
        "</table>",
        "<h2>Active Sessions</h2>",
        f"<p>{active_sessions} user(s) currently active</p>",
        "</body>",
        "</html>",
    ])

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def create_sample_log(path: str) -> None:
    """Create a sample log file for testing."""
    sample_lines = [
        "2024-01-01 12:00:00 INFO User 42 logged in",
        "2024-01-01 12:05:00 ERROR Database timeout",
        "2024-01-01 12:05:05 ERROR Database timeout",
        "2024-01-01 12:08:00 INFO API /users/profile took 250ms",
        "2024-01-01 12:09:00 WARN Memory usage at 87%",
        "2024-01-01 12:10:00 INFO User 42 logged out",
    ]
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(sample_lines) + "\n")


def run_pipeline() -> None:
    """
    Execute the complete ETL pipeline.

    Pipeline stages:
        1. Extract: Read log file
        2. Transform: Parse and categorize entries
        3. Load: Store aggregated metrics in database
        4. Report: Generate HTML output
    """
    config = Config.from_env()

    # Ensure log file exists for demo
    if not os.path.exists(config.log_file_path):
        print(f"Creating sample log file: {config.log_file_path}")
        create_sample_log(config.log_file_path)

    # Extract
    print(f"Reading log file: {config.log_file_path}")
    log_lines = extract(config.log_file_path)

    # Transform
    print("Parsing log entries...")
    parsed_data = transform(log_lines)

    # Aggregate
    error_counts = _count_errors(parsed_data.errors)
    api_stats = _compute_api_stats(parsed_data.api_calls)
    active_sessions = _count_active_sessions(parsed_data.user_actions)

    # Load
    print(f"Writing to database: {config.db_path}")
    load(config.db_path, error_counts, api_stats)

    # Report
    print("Generating report: report.html")
    generate_report(error_counts, api_stats, len(active_sessions))

    print(f"Pipeline completed at {datetime.datetime.now().isoformat()}")


if __name__ == "__main__":
    run_pipeline()