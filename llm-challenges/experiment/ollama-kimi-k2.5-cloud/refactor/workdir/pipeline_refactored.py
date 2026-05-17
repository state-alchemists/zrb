"""Log processing pipeline with ETL architecture.

Processes server logs and generates HTML reports with error summaries,
API latency metrics, and active session counts.
"""

from __future__ import annotations

import datetime
import os
import re
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


# =============================================================================
# Configuration
# =============================================================================


def load_config() -> dict[str, Any]:
    """Load configuration from environment variables.

    Returns:
        Dictionary containing all configuration values.

    Raises:
        ValueError: If a required environment variable is not set.
    """
    config: dict[str, Any] = {}

    config["db_path"] = _get_env("DB_PATH", "metrics.db")
    config["log_file"] = _get_env("LOG_FILE", "server.log")
    config["db_host"] = _get_env("DB_HOST", "localhost")
    config["db_port"] = int(_get_env("DB_PORT", "5432"))
    config["db_user"] = _get_env("DB_USER", "admin")
    config["db_pass"] = _get_env("DB_PASS", "password123")
    config["report_output"] = _get_env("REPORT_OUTPUT", "report.html")

    return config


def _get_env(key: str, default: str | None = None) -> str:
    """Get an environment variable, optionally with a default.

    Args:
        key: The environment variable name.
        default: Optional default value if not set.

    Returns:
        The environment variable value.

    Raises:
        ValueError: If the variable is not set and no default provided.
    """
    value = os.getenv(key, default)
    if value is None:
        raise ValueError(f"Environment variable {key} is required but not set")
    return value


# =============================================================================
# Data Models
# =============================================================================


@dataclass(frozen=True, slots=True)
class LogEntry:
    """Base class for parsed log entries."""

    timestamp: str
    level: str


@dataclass(frozen=True, slots=True)
class ErrorLogEntry(LogEntry):
    """Represents an ERROR level log entry."""

    message: str


@dataclass(frozen=True, slots=True)
class UserLogEntry(LogEntry):
    """Represents an INFO level user action log entry."""

    user_id: str
    action: str


@dataclass(frozen=True, slots=True)
class ApiLogEntry(LogEntry):
    """Represents an INFO level API call log entry."""

    endpoint: str
    duration_ms: int


@dataclass(frozen=True, slots=True)
class WarnLogEntry(LogEntry):
    """Represents a WARN level log entry."""

    message: str


LogRecord = ErrorLogEntry | UserLogEntry | ApiLogEntry | WarnLogEntry


@dataclass
class ProcessingResult:
    """Container for all data extracted from logs."""

    entries: list[LogRecord] = field(default_factory=list)
    sessions: dict[str, str] = field(default_factory=dict)
    api_calls: list[ApiLogEntry] = field(default_factory=list)
    errors: dict[str, int] = field(default_factory=dict)


# =============================================================================
# Log Parsing (EXTRACT Phase)
# =============================================================================

# Regex patterns for log line parsing
_LOG_PATTERN = re.compile(
    r"^(?P<timestamp>\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\s+"
    r"(?P<level>\w+)\s+"
    r"(?P<message>.+)$"
)

_USER_PATTERN = re.compile(
    r"User\s+(?P<user_id>\S+)\s+(?P<action>.+)$"
)

_API_PATTERN = re.compile(
    r"API\s+(?P<endpoint>\S+)\s+took\s+(?P<duration>\d+)ms"
)


def parse_log_line(line: str) -> LogRecord | None:
    """Parse a single log line into a typed record.

    Args:
        line: Raw log line from the file.

    Returns:
        A typed log entry or None if the line doesn't match expected formats.
    """
    match = _LOG_PATTERN.match(line.strip())
    if not match:
        return None

    timestamp = match.group("timestamp")
    level = match.group("level")
    message = match.group("message")

    match level:
        case "ERROR":
            return ErrorLogEntry(
                timestamp=timestamp,
                level=level,
                message=message,
            )
        case "WARN":
            return WarnLogEntry(
                timestamp=timestamp,
                level=level,
                message=message,
            )
        case "INFO":
            if "User" in message:
                user_match = _USER_PATTERN.search(message)
                if user_match:
                    return UserLogEntry(
                        timestamp=timestamp,
                        level=level,
                        user_id=user_match.group("user_id"),
                        action=user_match.group("action"),
                    )
            if "API" in message:
                api_match = _API_PATTERN.search(message)
                if api_match:
                    return ApiLogEntry(
                        timestamp=timestamp,
                        level=level,
                        endpoint=api_match.group("endpoint"),
                        duration_ms=int(api_match.group("duration")),
                    )
        case _:
            pass

    return None


def extract_log_data(log_path: Path | str) -> ProcessingResult:
    """Extract data from server log file.

    Args:
        log_path: Path to the log file.

    Returns:
        ProcessingResult containing all extracted and categorized data.
    """
    result = ProcessingResult()

    log_file = Path(log_path)
    if not log_file.exists():
        return result

    with open(log_file, "r", encoding="utf-8") as f:
        for line in f:
            entry = parse_log_line(line)
            if entry is None:
                continue

            result.entries.append(entry)

            match entry:
                case ApiLogEntry():
                    result.api_calls.append(entry)
                case ErrorLogEntry():
                    result.errors[entry.message] = result.errors.get(entry.message, 0) + 1
                case UserLogEntry():
                    if "logged in" in entry.action:
                        result.sessions[entry.user_id] = entry.timestamp
                    elif "logged out" in entry.action and entry.user_id in result.sessions:
                        del result.sessions[entry.user_id]
                case _:
                    pass

    return result


# =============================================================================
# Data Transformation (TRANSFORM Phase)
# =============================================================================


def calculate_api_stats(api_calls: list[ApiLogEntry]) -> dict[str, float]:
    """Calculate average latency per API endpoint.

    Args:
        api_calls: List of API call log entries.

    Returns:
        Dictionary mapping endpoint to average milliseconds.
    """
    endpoint_times: dict[str, list[int]] = {}
    for call in api_calls:
        endpoint_times.setdefault(call.endpoint, []).append(call.duration_ms)

    return {
        endpoint: sum(times) / len(times)
        for endpoint, times in endpoint_times.items()
    }


# =============================================================================
# Database Operations (LOAD Phase)
# =============================================================================


def init_database(db_path: Path | str) -> sqlite3.Connection:
    """Initialize database connection and schema.

    Args:
        db_path: Path to the SQLite database file.

    Returns:
        Database connection object.
    """
    conn = sqlite3.connect(str(db_path))
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
    return conn


def load_errors_to_db(
    conn: sqlite3.Connection,
    errors: dict[str, int],
) -> None:
    """Load error data into database using parameterized queries.

    Args:
        conn: Database connection.
        errors: Dictionary mapping error message to occurrence count.
    """
    cursor = conn.cursor()
    now = datetime.datetime.now().isoformat()

    for message, count in errors.items():
        cursor.execute(
            "INSERT INTO errors VALUES (?, ?, ?)",
            (now, message, count),
        )

    conn.commit()


def load_api_metrics_to_db(
    conn: sqlite3.Connection,
    api_stats: dict[str, float],
) -> None:
    """Load API metrics into database using parameterized queries.

    Args:
        conn: Database connection.
        api_stats: Dictionary mapping endpoint to average latency.
    """
    cursor = conn.cursor()
    now = datetime.datetime.now().isoformat()

    for endpoint, avg_ms in api_stats.items():
        cursor.execute(
            "INSERT INTO api_metrics VALUES (?, ?, ?)",
            (now, endpoint, avg_ms),
        )

    conn.commit()


# =============================================================================
# Report Generation
# =============================================================================


def generate_html_report(
    errors: dict[str, int],
    api_stats: dict[str, float],
    active_sessions: int,
) -> str:
    """Generate HTML report from processed data.

    Args:
        errors: Error message to count mapping.
        api_stats: Endpoint to average latency mapping.
        active_sessions: Number of currently active sessions.

    Returns:
        Complete HTML document as a string.
    """
    lines: list[str] = []

    lines.append("<!DOCTYPE html>")
    lines.append("<html>")
    lines.append("<head>")
    lines.append("<title>System Report</title>")
    lines.append("<style>")
    lines.append("table { border-collapse: collapse; }")
    lines.append("th, td { border: 1px solid #ccc; padding: 8px; }")
    lines.append("th { background-color: #f0f0f0; }")
    lines.append("</style>")
    lines.append("</head>")
    lines.append("<body>")

    # Error Summary
    lines.append("<h1>Error Summary</h1>")
    lines.append("<ul>")
    for err_msg, count in errors.items():
        lines.append(f"<li><b>{_escape_html(err_msg)}</b>: {count} occurrences</li>")
    lines.append("</ul>")

    # API Latency Table
    lines.append("<h2>API Latency</h2>")
    lines.append("<table>")
    lines.append("<tr><th>Endpoint</th><th>Avg (ms)</th></tr>")
    for endpoint, avg_ms in api_stats.items():
        lines.append(f"<tr><td>{_escape_html(endpoint)}</td><td>{avg_ms:.1f}</td></tr>")
    lines.append("</table>")

    # Active Sessions
    lines.append("<h2>Active Sessions</h2>")
    lines.append(f"<p>{active_sessions} user(s) currently active</p>")

    lines.append("</body>")
    lines.append("</html>")

    return "\n".join(lines)


def _escape_html(text: str) -> str:
    """Escape HTML special characters to prevent XSS.

    Args:
        text: Raw text that may contain HTML characters.

    Returns:
        Escaped text safe for HTML insertion.
    """
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def write_report(report_html: str, output_path: Path | str) -> None:
    """Write HTML report to file.

    Args:
        report_html: Complete HTML document.
        output_path: Path to write the report to.
    """
    Path(output_path).write_text(report_html, encoding="utf-8")


# =============================================================================
# Pipeline Orchestration
# =============================================================================


def run_pipeline(config: dict[str, Any]) -> None:
    """Execute the full ETL pipeline.

    Args:
        config: Configuration dictionary with all required settings.
    """
    log_file = config["log_file"]
    db_path = config["db_path"]
    report_output = config["report_output"]
    db_host = config["db_host"]
    db_port = config["db_port"]
    db_user = config["db_user"]

    print(f"Connecting to {db_host}:{db_port} as {db_user}...")

    # EXTRACT: Parse log file
    result = extract_log_data(log_file)

    # TRANSFORM: Calculate statistics
    api_stats = calculate_api_stats(result.api_calls)

    # LOAD: Store in database
    conn = init_database(db_path)
    try:
        load_errors_to_db(conn, result.errors)
        load_api_metrics_to_db(conn, api_stats)
    finally:
        conn.close()

    # GENERATE: Create HTML report
    report_html = generate_html_report(
        errors=result.errors,
        api_stats=api_stats,
        active_sessions=len(result.sessions),
    )
    write_report(report_html, report_output)

    print(f"Job finished at {datetime.datetime.now()}")


# =============================================================================
# Entry Point
# =============================================================================


def _create_sample_log(log_path: Path | str) -> None:
    """Create a sample log file for testing.

    Args:
        log_path: Path where the sample log should be created.
    """
    sample_lines = [
        "2024-01-01 12:00:00 INFO User 42 logged in\n",
        "2024-01-01 12:05:00 ERROR Database timeout\n",
        "2024-01-01 12:05:05 ERROR Database timeout\n",
        "2024-01-01 12:08:00 INFO API /users/profile took 250ms\n",
        "2024-01-01 12:09:00 WARN Memory usage at 87%\n",
        "2024-01-01 12:10:00 INFO User 42 logged out\n",
    ]
    Path(log_path).write_text("".join(sample_lines), encoding="utf-8")


def main() -> int:
    """Main entry point for the pipeline.

    Returns:
        Exit code (0 for success, 1 for failure).
    """
    try:
        config = load_config()
    except ValueError as e:
        print(f"Configuration error: {e}")
        return 1

    log_path = Path(config["log_file"])
    if not log_path.exists():
        _create_sample_log(log_path)

    run_pipeline(config)
    return 0


if __name__ == "__main__":
    exit(main())
