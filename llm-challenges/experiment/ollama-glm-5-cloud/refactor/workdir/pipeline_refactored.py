"""
Log processing pipeline for server metrics.

Extracts data from server logs, transforms into metrics,
loads into SQLite database, and generates HTML reports.

Environment Variables:
    DB_PATH: Path to SQLite database file (default: metrics.db)
    LOG_FILE: Path to server log file (default: server.log)
    DB_HOST: Database host (default: localhost)
    DB_PORT: Database port (default: 5432)
    DB_USER: Database user (default: admin)
    DB_PASS: Database password (default: "")

Usage:
    export DB_PATH=/path/to/db.sqlite
    export LOG_FILE=/var/log/server.log
    python pipeline_refactored.py
"""

import datetime
import os
import re
import sqlite3
from dataclasses import dataclass, field
from typing import Optional


# Configuration loaded from environment
@dataclass(frozen=True)
class Config:
    """Runtime configuration loaded from environment variables."""
    db_path: str = "metrics.db"
    log_file: str = "server.log"
    db_host: str = "localhost"
    db_port: int = 5432
    db_user: str = "admin"
    db_pass: str = ""

    @classmethod
    def from_env(cls) -> "Config":
        """Load configuration from environment variables."""
        return cls(
            db_path=os.getenv("DB_PATH", "metrics.db"),
            log_file=os.getenv("LOG_FILE", "server.log"),
            db_host=os.getenv("DB_HOST", "localhost"),
            db_port=int(os.getenv("DB_PORT", "5432")),
            db_user=os.getenv("DB_USER", "admin"),
            db_pass=os.getenv("DB_PASS", ""),
        )


# Regex patterns for log parsing
_LOG_PATTERN = re.compile(
    r"^(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) "
    r"(?P<level>INFO|WARN|ERROR) "
    r"(?P<message>.+)$"
)
_USER_ACTION_PATTERN = re.compile(r"User (?P<user_id>\S+) (?P<action>.+)$")
_API_PATTERN = re.compile(r"API (?P<endpoint>\S+)(?: took (?P<duration>\d+)ms)?")


@dataclass
class LogEntry:
    """Represents a parsed log entry."""
    timestamp: str
    level: str
    message: str


@dataclass
class ErrorRecord:
    """Error occurrence with count."""
    message: str
    count: int


@dataclass
class ApiMetric:
    """API endpoint latency metric."""
    endpoint: str
    avg_ms: float


@dataclass
class ParsedLogData:
    """Container for all parsed log data."""
    errors: list[ErrorRecord] = field(default_factory=list)
    api_metrics: list[ApiMetric] = field(default_factory=list)
    active_sessions: dict[str, str] = field(default_factory=dict)


# ---------------------------
# EXTRACT: Parse log files
# ---------------------------

def parse_log_line(line: str) -> Optional[LogEntry]:
    """
    Parse a single log line using regex.

    Args:
        line: Raw log line string.

    Returns:
        LogEntry if parsing succeeds, None otherwise.
    """
    match = _LOG_PATTERN.match(line.strip())
    if not match:
        return None
    return LogEntry(
        timestamp=match.group("timestamp"),
        level=match.group("level"),
        message=match.group("message"),
    )


def extract_user_action(message: str) -> Optional[tuple[str, str]]:
    """
    Extract user ID and action from user-related log messages.

    Args:
        message: The message portion of a log line containing 'User'.

    Returns:
        Tuple of (user_id, action) if matched, None otherwise.
    """
    match = _USER_ACTION_PATTERN.search(message)
    if not match:
        return None
    return match.group("user_id"), match.group("action").strip()


def extract_api_info(message: str) -> Optional[tuple[str, int]]:
    """
    Extract endpoint and duration from API log messages.

    Args:
        message: The message portion of a log line containing 'API'.

    Returns:
        Tuple of (endpoint, duration_ms) if matched, None otherwise.
    """
    match = _API_PATTERN.search(message)
    if not match:
        return None
    endpoint = match.group("endpoint")
    duration = int(match.group("duration") or 0)
    return endpoint, duration


def extract_log_data(log_file_path: str) -> ParsedLogData:
    """
    Extract and parse all data from the log file.

    Follows ETL Extract phase - reads raw log file and extracts
    structured data.

    Args:
        log_file_path: Path to the server log file.

    Returns:
        ParsedLogData containing errors, API metrics, and sessions.
    """
    result = ParsedLogData()
    error_counts: dict[str, int] = {}
    api_latencies: dict[str, list[int]] = {}

    if not os.path.exists(log_file_path):
        print(f"Warning: Log file not found: {log_file_path}")
        return result

    with open(log_file_path, "r", encoding="utf-8") as f:
        for line in f:
            entry = parse_log_line(line)
            if entry is None:
                continue

            if entry.level == "ERROR":
                error_counts[entry.message] = error_counts.get(entry.message, 0) + 1

            elif entry.level == "INFO":
                if "User" in entry.message:
                    user_info = extract_user_action(entry.message)
                    if user_info:
                        user_id, action = user_info
                        if "logged in" in action:
                            result.active_sessions[user_id] = entry.timestamp
                        elif "logged out" in action:
                            result.active_sessions.pop(user_id, None)

                elif "API" in entry.message:
                    api_info = extract_api_info(entry.message)
                    if api_info:
                        endpoint, duration = api_info
                        api_latencies.setdefault(endpoint, []).append(duration)

            elif entry.level == "WARN":
                # Track warnings as errors for now
                error_counts[entry.message] = error_counts.get(entry.message, 0) + 1

    # Transform error counts into records
    for msg, count in error_counts.items():
        result.errors.append(ErrorRecord(message=msg, count=count))

    # Calculate average latencies
    for endpoint, latencies in api_latencies.items():
        avg = sum(latencies) / len(latencies) if latencies else 0.0
        result.api_metrics.append(ApiMetric(endpoint=endpoint, avg_ms=avg))

    return result


# ---------------------------
# TRANSFORM: Process data
# ---------------------------

def transform_errors(errors: list[ErrorRecord]) -> dict[str, int]:
    """
    Transform error records into a summary dictionary.

    Args:
        errors: List of ErrorRecord objects.

    Returns:
        Dictionary mapping error message to occurrence count.
    """
    return {e.message: e.count for e in errors}


def transform_api_metrics(metrics: list[ApiMetric]) -> dict[str, float]:
    """
    Transform API metrics into a summary dictionary.

    Args:
        metrics: List of ApiMetric objects.

    Returns:
        Dictionary mapping endpoint to average latency in ms.
    """
    return {m.endpoint: m.avg_ms for m in metrics}


# ---------------------------
# LOAD: Write to database and files
# ---------------------------

def init_database(conn: sqlite3.Connection) -> None:
    """
    Initialize database tables if they don't exist.

    Args:
        conn: SQLite database connection.
    """
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


def load_errors(
    conn: sqlite3.Connection,
    errors: list[ErrorRecord],
    timestamp: str
) -> None:
    """
    Load error records into the database using parameterized queries.

    Args:
        conn: SQLite database connection.
        errors: List of ErrorRecord objects to insert.
        timestamp: Timestamp for the records.
    """
    cursor = conn.cursor()
    for error in errors:
        cursor.execute(
            "INSERT INTO errors (dt, message, count) VALUES (?, ?, ?)",
            (timestamp, error.message, error.count)
        )
    conn.commit()


def load_api_metrics(
    conn: sqlite3.Connection,
    metrics: list[ApiMetric],
    timestamp: str
) -> None:
    """
    Load API metrics into the database using parameterized queries.

    Args:
        conn: SQLite database connection.
        metrics: List of ApiMetric objects to insert.
        timestamp: Timestamp for the records.
    """
    cursor = conn.cursor()
    for metric in metrics:
        cursor.execute(
            "INSERT INTO api_metrics (dt, endpoint, avg_ms) VALUES (?, ?, ?)",
            (timestamp, metric.endpoint, metric.avg_ms)
        )
    conn.commit()


def load_to_database(
    data: ParsedLogData,
    db_path: str,
    db_host: str,
    db_port: int,
    db_user: str
) -> None:
    """
    Load processed data into the SQLite database.

    Note: db_host, db_port, and db_user are logged for audit purposes
    but SQLite uses file-based storage.

    Args:
        data: Parsed log data to load.
        db_path: Path to SQLite database file.
        db_host: Database host (for logging).
        db_port: Database port (for logging).
        db_user: Database user (for logging).
    """
    timestamp = datetime.datetime.now().isoformat()
    print(f"Connecting to {db_host}:{db_port} as {db_user}...")

    conn = sqlite3.connect(db_path)
    try:
        init_database(conn)
        load_errors(conn, data.errors, timestamp)
        load_api_metrics(conn, data.api_metrics, timestamp)
    finally:
        conn.close()


def generate_report(
    errors: list[ErrorRecord],
    api_metrics: list[ApiMetric],
    active_sessions: dict[str, str],
    output_path: str
) -> None:
    """
    Generate an HTML report from the processed data.

    Args:
        errors: List of error records.
        api_metrics: List of API metrics.
        active_sessions: Dictionary of active user sessions.
        output_path: Path to write the HTML report.
    """
    lines = [
        "<!DOCTYPE html>",
        "<html>",
        "<head>",
        "  <title>System Report</title>",
        "  <style>",
        "    body { font-family: Arial, sans-serif; margin: 20px; }",
        "    table { border-collapse: collapse; }",
        "    th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }",
        "    th { background-color: #f2f2f2; }",
        "  </style>",
        "</head>",
        "<body>",
        "  <h1>Error Summary</h1>",
        "  <ul>",
    ]

    for error in errors:
        lines.append(f"    <li><b>{error.message}</b>: {error.count} occurrences</li>")

    lines.extend([
        "  </ul>",
        "",
        "  <h2>API Latency</h2>",
        "  <table>",
        "    <tr><th>Endpoint</th><th>Avg (ms)</th></tr>",
    ])

    for metric in api_metrics:
        lines.append(f"    <tr><td>{metric.endpoint}</td><td>{metric.avg_ms:.1f}</td></tr>")

    lines.extend([
        "  </table>",
        "",
        "  <h2>Active Sessions</h2>",
        f"  <p>{len(active_sessions)} user(s) currently active</p>",
        "</body>",
        "</html>",
    ])

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


# ---------------------------
# Main Pipeline
# ---------------------------

def run_pipeline(config: Optional[Config] = None) -> None:
    """
    Execute the complete ETL pipeline.

    Args:
        config: Configuration object. If None, loads from environment.
    """
    if config is None:
        config = Config.from_env()

    # Extract: Parse log file
    print(f"Processing log file: {config.log_file}")
    data = extract_log_data(config.log_file)

    # Transform: Already done during extraction
    # (data structures are in final form)

    # Load: Write to database
    load_to_database(
        data,
        config.db_path,
        config.db_host,
        config.db_port,
        config.db_user
    )

    # Generate report
    report_path = os.path.join(os.path.dirname(config.db_path), "report.html")
    generate_report(data.errors, data.api_metrics, data.active_sessions, report_path)

    print(f"Pipeline completed at {datetime.datetime.now()}")


def create_sample_log_file(path: str) -> None:
    """
    Create a sample log file for testing.

    Args:
        path: Path to write the sample log file.
    """
    sample_lines = [
        "2024-01-01 12:00:00 INFO User user_42 logged in",
        "2024-01-01 12:05:00 ERROR Database timeout",
        "2024-01-01 12:05:05 ERROR Database timeout",
        "2024-01-01 12:08:00 INFO API /users/profile took 250ms",
        "2024-01-01 12:09:00 WARN Memory usage at 87%",
        "2024-01-01 12:10:00 INFO User user_42 logged out",
    ]
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(sample_lines) + "\n")


if __name__ == "__main__":
    config = Config.from_env()

    # Create sample log file if it doesn't exist
    if not os.path.exists(config.log_file):
        print(f"Creating sample log file: {config.log_file}")
        create_sample_log_file(config.log_file)

    run_pipeline(config)