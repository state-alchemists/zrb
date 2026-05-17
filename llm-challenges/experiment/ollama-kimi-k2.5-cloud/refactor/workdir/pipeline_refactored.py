#!/usr/bin/env python3
"""
Server Log Pipeline - Refactored

ETL pipeline for processing server logs and generating HTML reports.
Uses environment variables for configuration and parameterized queries for safety.
"""

import datetime
import os
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

# =============================================================================
# Configuration - loaded from environment variables
# =============================================================================

ENV_VARS = {
    "DB_PATH": ("metrics.db", "Path to SQLite database file"),
    "LOG_FILE": ("server.log", "Path to server log file"),
    "DB_HOST": ("localhost", "Database host (for display only with SQLite)"),
    "DB_PORT": ("5432", "Database port (for display only with SQLite)"),
    "DB_USER": ("admin", "Database user (for display only with SQLite)"),
    "DB_PASS": ("", "Database password (for display only with SQLite)"),
    "REPORT_OUTPUT": ("report.html", "Path for HTML report output"),
}


class ConfigurationError(Exception):
    """Raised when required configuration is missing or invalid."""
    pass


def load_config() -> dict[str, str]:
    """Load configuration from environment variables with fallback defaults.

    Returns:
        Dictionary of configuration values.

    Raises:
        ConfigurationError: If a required environment variable is missing.
    """
    config = {}
    for key, (default, description) in ENV_VARS.items():
        value = os.environ.get(key, default)
        if not value and key in ("DB_PATH", "LOG_FILE"):
            raise ConfigurationError(
                f"Required configuration '{key}' ({description}) is not set"
            )
        config[key] = value
    return config


# =============================================================================
# Data Models
# =============================================================================

@dataclass
class LogEntry:
    """Base class for parsed log entries."""
    timestamp: str
    level: str


@dataclass
class ErrorEntry(LogEntry):
    """Represents an error log entry."""
    message: str


@dataclass
class UserSessionEntry(LogEntry):
    """Represents a user login/logout event."""
    user_id: str
    action: str


@dataclass
class ApiCallEntry(LogEntry):
    """Represents an API call with latency information."""
    endpoint: str
    duration_ms: int


@dataclass
class WarningEntry(LogEntry):
    """Represents a warning log entry."""
    message: str


# Union type for all log entry types
LogEntryType = ErrorEntry | UserSessionEntry | ApiCallEntry | WarningEntry


# =============================================================================
# Extract: Log Parsing
# =============================================================================

# Regex patterns for parsing log lines
LOG_LINE_PATTERN = re.compile(
    r"^(?P<timestamp>\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})"
    r"\s+(?P<level>\w+)"
    r"\s+(?P<message>.+)$"
)

USER_ACTION_PATTERN = re.compile(
    r"User\s+(?P<user_id>\S+)\s+(?P<action>.+)"
)

API_CALL_PATTERN = re.compile(
    r"API\s+(?P<endpoint>\S+)"
    r"(?:\s+took\s+(?P<duration>\d+)ms)?"
)


def extract_log_data(log_file_path: str) -> list[LogEntryType]:
    """Extract structured data from server log file.

    Args:
        log_file_path: Path to the log file to parse.

    Returns:
        List of parsed log entries.
    """
    entries: list[LogEntryType] = []
    path = Path(log_file_path)

    if not path.exists():
        return entries

    with open(path, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue

            entry = _parse_log_line(line)
            if entry:
                entries.append(entry)

    return entries


def _parse_log_line(line: str) -> Optional[LogEntryType]:
    """Parse a single log line using regex patterns.

    Args:
        line: A single line from the log file.

    Returns:
        Parsed log entry or None if parsing fails.
    """
    match = LOG_LINE_PATTERN.match(line)
    if not match:
        return None

    timestamp = match.group("timestamp")
    level = match.group("level")
    message = match.group("message")

    if level == "ERROR":
        return ErrorEntry(timestamp=timestamp, level=level, message=message)

    if level == "WARN":
        return WarningEntry(timestamp=timestamp, level=level, message=message)

    if level == "INFO":
        # Try to parse as user action
        user_match = USER_ACTION_PATTERN.search(message)
        if user_match:
            return UserSessionEntry(
                timestamp=timestamp,
                level=level,
                user_id=user_match.group("user_id"),
                action=user_match.group("action"),
            )

        # Try to parse as API call
        api_match = API_CALL_PATTERN.search(message)
        if api_match:
            duration_str = api_match.group("duration")
            return ApiCallEntry(
                timestamp=timestamp,
                level=level,
                endpoint=api_match.group("endpoint"),
                duration_ms=int(duration_str) if duration_str else 0,
            )

    return None


# =============================================================================
# Transform: Data Processing
# =============================================================================

@dataclass
class TransformResult:
    """Result of the transform phase containing processed data."""
    error_counts: dict[str, int]
    api_latencies: dict[str, list[int]]
    active_sessions: dict[str, str]
    api_averages: dict[str, float]


def transform_log_entries(entries: list[LogEntryType]) -> TransformResult:
    """Transform raw log entries into aggregated metrics.

    Args:
        entries: List of parsed log entries.

    Returns:
        Aggregated metrics ready for loading.
    """
    error_counts: dict[str, int] = {}
    api_latencies: dict[str, list[int]] = {}
    active_sessions: dict[str, str] = {}

    for entry in entries:
        if isinstance(entry, ErrorEntry):
            error_counts[entry.message] = error_counts.get(entry.message, 0) + 1

        elif isinstance(entry, UserSessionEntry):
            if "logged in" in entry.action:
                active_sessions[entry.user_id] = entry.timestamp
            elif "logged out" in entry.action and entry.user_id in active_sessions:
                del active_sessions[entry.user_id]

        elif isinstance(entry, ApiCallEntry):
            if entry.endpoint not in api_latencies:
                api_latencies[entry.endpoint] = []
            api_latencies[entry.endpoint].append(entry.duration_ms)

    # Calculate averages
    api_averages = {
        endpoint: sum(times) / len(times)
        for endpoint, times in api_latencies.items()
    }

    return TransformResult(
        error_counts=error_counts,
        api_latencies=api_latencies,
        active_sessions=active_sessions,
        api_averages=api_averages,
    )


# =============================================================================
# Load: Database Operations
# =============================================================================

class DatabaseLoader:
    """Handles database connections and data loading with parameterized queries."""

    def __init__(self, db_path: str) -> None:
        """Initialize the database loader.

        Args:
            db_path: Path to the SQLite database file.
        """
        self.db_path = db_path
        self.conn: Optional[sqlite3.Connection] = None
        self.cursor: Optional[sqlite3.Cursor] = None

    def __enter__(self) -> "DatabaseLoader":
        """Context manager entry - opens connection and creates tables."""
        self.connect()
        self._create_tables()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit - commits and closes connection."""
        self.close()

    def connect(self) -> None:
        """Establish database connection."""
        self.conn = sqlite3.connect(self.db_path)
        self.cursor = self.conn.cursor()

    def close(self) -> None:
        """Close database connection, committing any pending changes."""
        if self.conn:
            self.conn.commit()
            self.conn.close()
            self.conn = None
            self.cursor = None

    def _create_tables(self) -> None:
        """Create required database tables if they don't exist."""
        if not self.cursor:
            raise RuntimeError("Database not connected")

        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS errors (
                dt TEXT,
                message TEXT,
                count INTEGER
            )
        """)
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS api_metrics (
                dt TEXT,
                endpoint TEXT,
                avg_ms REAL
            )
        """)

    def load_errors(self, error_counts: dict[str, int]) -> None:
        """Load error counts into database using parameterized queries.

        Args:
            error_counts: Dictionary mapping error messages to occurrence counts.
        """
        if not self.cursor:
            raise RuntimeError("Database not connected")

        now = datetime.datetime.now().isoformat()
        # Use parameterized query to prevent SQL injection
        for message, count in error_counts.items():
            self.cursor.execute(
                "INSERT INTO errors (dt, message, count) VALUES (?, ?, ?)",
                (now, message, count),
            )

    def load_api_metrics(self, api_averages: dict[str, float]) -> None:
        """Load API latency metrics into database using parameterized queries.

        Args:
            api_averages: Dictionary mapping endpoints to average latency.
        """
        if not self.cursor:
            raise RuntimeError("Database not connected")

        now = datetime.datetime.now().isoformat()
        # Use parameterized query to prevent SQL injection
        for endpoint, avg_ms in api_averages.items():
            self.cursor.execute(
                "INSERT INTO api_metrics (dt, endpoint, avg_ms) VALUES (?, ?, ?)",
                (now, endpoint, avg_ms),
            )


# =============================================================================
# Report Generation
# =============================================================================

def generate_html_report(
    data: TransformResult,
    output_path: str,
) -> None:
    """Generate HTML report from transformed data.

    Args:
        data: Transformed metrics containing error counts, API latencies,
            and active sessions.
        output_path: Path where the HTML report will be written.
    """
    lines = [
        "<html>",
        "<head><title>System Report</title></head>",
        "<body>",
        "",
        "    <h1>Error Summary</h1>",
        "    <ul>",
    ]

    for err_msg, count in data.error_counts.items():
        escaped_msg = _escape_html(err_msg)
        lines.append(f"        <li><b>{escaped_msg}</b>: {count} occurrences</li>")

    lines.extend([
        "    </ul>",
        "",
        "    <h2>API Latency</h2>",
        "    <table border='1'>",
        "        <tr><th>Endpoint</th><th>Avg (ms)</th></tr>",
    ])

    for ep, avg in data.api_averages.items():
        escaped_ep = _escape_html(ep)
        lines.append(
            f"        <tr><td>{escaped_ep}</td><td>{round(avg, 1)}</td></tr>"
        )

    lines.extend([
        "    </table>",
        "",
        "    <h2>Active Sessions</h2>",
        f"    <p>{len(data.active_sessions)} user(s) currently active</p>",
        "</body>",
        "</html>",
    ])

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def _escape_html(text: str) -> str:
    """Escape special HTML characters to prevent XSS.

    Args:
        text: Raw text that may contain HTML special characters.

    Returns:
        Text with HTML special characters escaped.
    """
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


# =============================================================================
# Pipeline Orchestration
# =============================================================================

def run_pipeline(config: dict[str, str]) -> None:
    """Execute the ETL pipeline with the given configuration.

    Args:
        config: Dictionary containing pipeline configuration values.
    """
    db_path = config["DB_PATH"]
    log_file = config["LOG_FILE"]
    report_output = config["REPORT_OUTPUT"]
    db_host = config["DB_HOST"]
    db_port = config["DB_PORT"]
    db_user = config["DB_USER"]

    print(f"Connecting to {db_host}:{db_port} as {db_user}...")

    # EXTRACT: Parse log file into structured entries
    entries = extract_log_data(log_file)

    # TRANSFORM: Aggregate and process the extracted data
    transformed = transform_log_entries(entries)

    # LOAD: Store metrics in database with parameterized queries
    with DatabaseLoader(db_path) as loader:
        loader.load_errors(transformed.error_counts)
        loader.load_api_metrics(transformed.api_averages)

    # Generate HTML report
    generate_html_report(transformed, report_output)

    print(f"Job finished at {datetime.datetime.now()}")
    print(f"Report generated: {report_output}")


def create_sample_log_file(log_file_path: str) -> None:
    """Create a sample log file for testing if one doesn't exist.

    Args:
        log_file_path: Path where the sample log file will be created.
    """
    path = Path(log_file_path)
    if path.exists():
        return

    sample_lines = [
        "2024-01-01 12:00:00 INFO User 42 logged in\n",
        "2024-01-01 12:05:00 ERROR Database timeout\n",
        "2024-01-01 12:05:05 ERROR Database timeout\n",
        "2024-01-01 12:08:00 INFO API /users/profile took 250ms\n",
        "2024-01-01 12:09:00 WARN Memory usage at 87%\n",
        "2024-01-01 12:10:00 INFO User 42 logged out\n",
    ]

    with open(path, "w", encoding="utf-8") as f:
        f.writelines(sample_lines)

    print(f"Created sample log file: {log_file_path}")


# =============================================================================
# Entry Point
# =============================================================================

def main() -> None:
    """Main entry point for the pipeline."""
    # Load configuration from environment
    config = load_config()

    # Create sample data if needed
    create_sample_log_file(config["LOG_FILE"])

    # Run the pipeline
    run_pipeline(config)


if __name__ == "__main__":
    main()
