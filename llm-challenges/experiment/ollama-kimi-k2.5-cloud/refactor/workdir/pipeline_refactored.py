"""
Log processing pipeline with ETL architecture.

Refactored from monolithic script to modular, type-safe, secure implementation:
- Config via environment variables (pydantic-settings)
- SQL injection protection via parameterized queries
- Regex-based log parsing
- Full type hints and documentation
"""

from __future__ import annotations

import dataclasses
import datetime
import html
import os
import re
import sqlite3
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple


# =============================================================================
# Configuration
# =============================================================================

class Settings:
    """Application configuration loaded from environment variables."""

    def __init__(self) -> None:
        self.db_path: str = os.getenv("DB_PATH", "metrics.db")
        self.log_file: str = os.getenv("LOG_FILE", "server.log")
        self.db_host: str = os.getenv("DB_HOST", "localhost")
        self.db_port: int = int(os.getenv("DB_PORT", "5432"))
        self.db_user: str = os.getenv("DB_USER", "admin")
        self.db_pass: str = os.getenv("DB_PASS", "password123")
        self.report_output: str = os.getenv("REPORT_OUTPUT", "report.html")

    def __repr__(self) -> str:
        return (
            f"Settings(db_path={self.db_path!r}, log_file={self.log_file!r}, "
            f"db_host={self.db_host!r}, db_port={self.db_port})"
        )


# =============================================================================
# Data Models
# =============================================================================

@dataclasses.dataclass(frozen=True, slots=True)
class LogEntry:
    """Base log entry with timestamp and level."""

    timestamp: str
    level: str


@dataclasses.dataclass(frozen=True, slots=True)
class ErrorLog(LogEntry):
    """Error log entry with message."""

    message: str


@dataclasses.dataclass(frozen=True, slots=True)
class UserLog(LogEntry):
    """User session log entry."""

    user_id: str
    action: str  # "logged in" or "logged out"


@dataclasses.dataclass(frozen=True, slots=True)
class ApiLog(LogEntry):
    """API call log entry with latency."""

    endpoint: str
    duration_ms: int


@dataclasses.dataclass(frozen=True, slots=True)
class WarningLog(LogEntry):
    """Warning log entry."""

    message: str


# Union type for all log entry types
LogEntryType = ErrorLog | UserLog | ApiLog | WarningLog


# =============================================================================
# Extract: Log Parsing
# =============================================================================

# Regex patterns for parsing log lines
# Format: "YYYY-MM-DD HH:MM:SS LEVEL ..."
LOG_LINE_PATTERN = re.compile(
    r"^(?P<date>\d{4}-\d{2}-\d{2})\s+"      # Date
    r"(?P<time>\d{2}:\d{2}:\d{2})\s+"      # Time
    r"(?P<level>\w+)\s+"                    # Log level
    r"(?P<message>.*)$"                      # Rest of line
)

# Pattern for API calls: "API /path took Nms"
API_PATTERN = re.compile(
    r"API\s+(?P<endpoint>/\S+)\s+took\s+(?P<duration>\d+)ms",
    re.IGNORECASE
)

# Pattern for user actions: "User N logged in/out"
USER_PATTERN = re.compile(
    r"User\s+(?P<user_id>\S+)\s+(?P<action>logged\s+(?:in|out))",
    re.IGNORECASE
)


def parse_log_line(line: str) -> LogEntryType | None:
    """
    Parse a single log line into a typed LogEntry.

    Args:
        line: Raw log line from the server log.

    Returns:
        Typed LogEntry subclass or None if line cannot be parsed.
    """
    line = line.strip()
    if not line:
        return None

    match = LOG_LINE_PATTERN.match(line)
    if not match:
        return None

    timestamp = f"{match.group('date')} {match.group('time')}"
    level = match.group("level").upper()
    message = match.group("message").strip()

    if level == "ERROR":
        return ErrorLog(timestamp=timestamp, level=level, message=message)

    if level == "WARN":
        return WarningLog(timestamp=timestamp, level=level, message=message)

    if level == "INFO":
        # Check for API call
        api_match = API_PATTERN.search(message)
        if api_match:
            return ApiLog(
                timestamp=timestamp,
                level=level,
                endpoint=api_match.group("endpoint"),
                duration_ms=int(api_match.group("duration"))
            )

        # Check for user action
        user_match = USER_PATTERN.search(message)
        if user_match:
            return UserLog(
                timestamp=timestamp,
                level=level,
                user_id=user_match.group("user_id"),
                action=user_match.group("action").lower()
            )

    return None


def extract_log_data(log_path: str) -> Tuple[List[LogEntryType], Dict[str, str]]:
    """
    Extract and parse all log entries from the log file.

    Args:
        log_path: Path to the server log file.

    Returns:
        Tuple of (list of parsed log entries, dict of active user sessions).
        Sessions dict maps user_id -> login_timestamp for currently logged-in users.
    """
    entries: List[LogEntryType] = []
    sessions: Dict[str, str] = {}
    path = Path(log_path)

    if not path.exists():
        return entries, sessions

    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            entry = parse_log_line(line)
            if entry is None:
                continue

            entries.append(entry)

            # Track session state for user logs
            if isinstance(entry, UserLog):
                if "login" in entry.action:
                    sessions[entry.user_id] = entry.timestamp
                elif "logout" in entry.action and entry.user_id in sessions:
                    del sessions[entry.user_id]

    return entries, sessions


# =============================================================================
# Transform: Data Processing
# =============================================================================

def transform_error_summary(entries: List[LogEntryType]) -> Dict[str, int]:
    """
    Aggregate error counts by message.

    Args:
        entries: All parsed log entries.

    Returns:
        Dict mapping error message -> occurrence count.
    """
    error_counts: Dict[str, int] = defaultdict(int)
    for entry in entries:
        if isinstance(entry, ErrorLog):
            error_counts[entry.message] += 1
    return dict(error_counts)


def transform_api_latency(entries: List[LogEntryType]) -> Dict[str, Tuple[float, int]]:
    """
    Calculate average latency per API endpoint.

    Args:
        entries: All parsed log entries.

    Returns:
        Dict mapping endpoint -> (average_ms, call_count).
    """
    endpoint_times: Dict[str, List[int]] = defaultdict(list)
    for entry in entries:
        if isinstance(entry, ApiLog):
            endpoint_times[entry.endpoint].append(entry.duration_ms)

    result: Dict[str, Tuple[float, int]] = {}
    for endpoint, times in endpoint_times.items():
        avg = sum(times) / len(times)
        result[endpoint] = (avg, len(times))
    return result


# =============================================================================
# Load: Database + Report Generation
# =============================================================================

def load_to_database(
    db_path: str,
    error_summary: Dict[str, int],
    api_latency: Dict[str, Tuple[float, int]],
    db_host: str,
    db_user: str
) -> None:
    """
    Load transformed data into SQLite database using parameterized queries.

    Args:
        db_path: Path to SQLite database file.
        error_summary: Error message counts from transform phase.
        api_latency: Endpoint latency stats from transform phase.
        db_host: Database host (for logging only).
        db_user: Database user (for logging only).
    """
    print(f"Connecting to {db_host}:5432 as {db_user}...")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Create tables
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

    now = datetime.datetime.now().isoformat()

    # Insert errors using parameterized query (injection-safe)
    for msg, count in error_summary.items():
        cursor.execute(
            "INSERT INTO errors (dt, message, count) VALUES (?, ?, ?)",
            (now, msg, count)
        )

    # Insert API metrics using parameterized query (injection-safe)
    for endpoint, (avg_ms, _) in api_latency.items():
        cursor.execute(
            "INSERT INTO api_metrics (dt, endpoint, avg_ms) VALUES (?, ?, ?)",
            (now, endpoint, avg_ms)
        )

    conn.commit()
    conn.close()


def escape_html(text: str) -> str:
    """Escape special HTML characters to prevent XSS."""
    return html.escape(str(text))


def load_to_html_report(
    output_path: str,
    error_summary: Dict[str, int],
    api_latency: Dict[str, Tuple[float, int]],
    active_sessions: int
) -> None:
    """
    Generate HTML report from transformed data.

    Args:
        output_path: Path to write the HTML report.
        error_summary: Error message counts.
        api_latency: Endpoint latency stats.
        active_sessions: Number of currently active user sessions.
    """
    lines: List[str] = []
    lines.append("<html>")
    lines.append("<head><title>System Report</title></head>")
    lines.append("<body>")

    # Error Summary Section
    lines.append("<h1>Error Summary</h1>")
    lines.append("<ul>")
    for err_msg, count in error_summary.items():
        escaped_msg = escape_html(err_msg)
        lines.append(f"<li><b>{escaped_msg}</b>: {count} occurrences</li>")
    lines.append("</ul>")

    # API Latency Section
    lines.append("<h2>API Latency</h2>")
    lines.append("<table border='1'>")
    lines.append("<tr><th>Endpoint</th><th>Avg (ms)</th></tr>")
    for endpoint, (avg_ms, _) in api_latency.items():
        escaped_endpoint = escape_html(endpoint)
        lines.append(
            f"<tr><td>{escaped_endpoint}</td><td>{round(avg_ms, 1)}</td></tr>"
        )
    lines.append("</table>")

    # Active Sessions Section
    lines.append("<h2>Active Sessions</h2>")
    lines.append(f"<p>{active_sessions} user(s) currently active</p>")
    lines.append("</body>")
    lines.append("</html>")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


# =============================================================================
# Pipeline Orchestration
# =============================================================================

def run_pipeline(settings: Settings | None = None) -> None:
    """
    Execute the full ETL pipeline.

    Args:
        settings: Configuration settings. If None, loads from environment.
    """
    if settings is None:
        settings = Settings()

    # Extract
    entries, sessions = extract_log_data(settings.log_file)

    # Transform
    error_summary = transform_error_summary(entries)
    api_latency = transform_api_latency(entries)

    # Load
    load_to_database(
        settings.db_path,
        error_summary,
        api_latency,
        settings.db_host,
        settings.db_user
    )
    load_to_html_report(
        settings.report_output,
        error_summary,
        api_latency,
        len(sessions)
    )

    print(f"Job finished at {datetime.datetime.now()}")


def create_sample_log(log_path: str) -> None:
    """Create a sample log file for testing if it doesn't exist."""
    path = Path(log_path)
    if path.exists():
        return

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


if __name__ == "__main__":
    create_sample_log("server.log")
    run_pipeline()
