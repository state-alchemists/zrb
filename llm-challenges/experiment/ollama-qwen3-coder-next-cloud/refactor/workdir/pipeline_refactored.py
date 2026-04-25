"""
ETL pipeline for server log processing.

This script reads server logs, extracts structured data, transforms it into
metrics, and loads results into a SQLite database. Configuration is read from
environment variables.

Environment Variables:
    DB_PATH: Path to the SQLite database (default: metrics.db)
    LOG_FILE: Path to the server log file (default: server.log)
    DB_HOST: Database host for informational purposes only
    DB_PORT: Database port for informational purposes only
    DB_USER: Database user for informational purposes only
    DB_PASS: Database password for informational purposes only
"""

import datetime
import os
import re
import sqlite3
from dataclasses import dataclass
from typing import Optional


# =============================================================================
# Configuration
# =============================================================================

@dataclass
class Config:
    """Configuration loaded from environment variables."""
    db_path: str = os.getenv("DB_PATH", "metrics.db")
    log_file: str = os.getenv("LOG_FILE", "server.log")
    db_host: str = os.getenv("DB_HOST", "localhost")
    db_port: str = os.getenv("DB_PORT", "5432")
    db_user: str = os.getenv("DB_USER", "admin")
    db_pass: str = os.getenv("DB_PASS", "password123")


config = Config()


# =============================================================================
# Log Parsing (Extraction)
# =============================================================================

# Regex patterns for log line parsing
# Format: YYYY-MM-DD HH:MM:SS LEVEL Message
LOG_LINE_PATTERN = re.compile(
    r"^(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2}:\d{2})\s+(.+)$"
)

# ERROR line: just date time and message
ERROR_PATTERN = re.compile(r"ERROR\s+(.+)$")

# INFO User line: User <uid> <action>
USER_LOG_PATTERN = re.compile(r"INFO\s+User\s+(\d+)\s+(.+)$")

# INFO API line: API <endpoint> took <ms>ms
API_LOG_PATTERN = re.compile(r"INFO\s+API\s+(\S+)\s+took\s+(\d+)ms")

# WARN line: just message after WARN
WARN_PATTERN = re.compile(r"WARN\s+(.+)$")


@dataclass
class ErrorEntry:
    """Reparsed error log entry."""
    datetime: str
    message: str


@dataclass
class UserEntry:
    """Reparsed user log entry."""
    datetime: str
    user_id: str
    action: str


@dataclass
class ApiEntry:
    """Reparsed API log entry."""
    datetime: str
    endpoint: str
    duration_ms: int


@dataclass
class WarnEntry:
    """Reparsed warning log entry."""
    datetime: str
    message: str


def parse_log_line(line: str) -> Optional[ErrorEntry | UserEntry | ApiEntry | WarnEntry]:
    """
    Parse a single log line and return an appropriate entry object.
    
    Uses regex patterns to extract structured data from log entries.
    
    Args:
        line: A single line from the server log file.
        
    Returns:
        An entry object (ErrorEntry, UserEntry, ApiEntry, or WarnEntry) or
        None if the line doesn't match any known format.
    """
    match = LOG_LINE_PATTERN.match(line.strip())
    if not match:
        return None
    
    date_part, time_part, rest = match.groups()
    datetime_str = f"{date_part} {time_part}"
    
    # ERROR line
    error_match = ERROR_PATTERN.match(rest)
    if error_match:
        return ErrorEntry(datetime=datetime_str, message=error_match.group(1).strip())
    
    # User action line
    user_match = USER_LOG_PATTERN.match(rest)
    if user_match:
        user_id, action = user_match.groups()
        return UserEntry(datetime=datetime_str, user_id=user_id, action=action.strip())
    
    # API call line
    api_match = API_LOG_PATTERN.match(rest)
    if api_match:
        endpoint, duration = api_match.groups()
        return ApiEntry(datetime=datetime_str, endpoint=endpoint, duration_ms=int(duration))
    
    # WARN line
    warn_match = WARN_PATTERN.match(rest)
    if warn_match:
        return WarnEntry(datetime=datetime_str, message=warn_match.group(1).strip())
    
    return None


def extract_logs(log_file: str) -> tuple[list[ErrorEntry], list[ApiEntry], list[UserEntry], list[WarnEntry]]:
    """
    Extract structured data from the log file.
    
    Args:
        log_file: Path to the server log file.
        
    Returns:
        A tuple of lists containing ErrorEntry, ApiEntry, UserEntry, and WarnEntry.
    """
    errors: list[ErrorEntry] = []
    apis: list[ApiEntry] = []
    users: list[UserEntry] = []
    warns: list[WarnEntry] = []
    
    if not os.path.exists(log_file):
        return errors, apis, users, warns
    
    with open(log_file, "r") as f:
        for line in f:
            entry = parse_log_line(line)
            if isinstance(entry, ErrorEntry):
                errors.append(entry)
            elif isinstance(entry, ApiEntry):
                apis.append(entry)
            elif isinstance(entry, UserEntry):
                users.append(entry)
            elif isinstance(entry, WarnEntry):
                warns.append(entry)
    
    return errors, apis, users, warns


# =============================================================================
# Data Transformation
# =============================================================================

def transform_errors(errors: list[ErrorEntry]) -> dict[str, int]:
    """
    Aggregate error counts by message.
    
    Args:
        errors: List of ErrorEntry objects.
        
    Returns:
        A dictionary mapping error messages to their occurrence counts.
    """
    counts: dict[str, int] = {}
    for error in errors:
        counts[error.message] = counts.get(error.message, 0) + 1
    return counts


def transform_api_metrics(apis: list[ApiEntry]) -> dict[str, float]:
    """
    Calculate average latency per API endpoint.
    
    Args:
        apis: List of ApiEntry objects.
        
    Returns:
        A dictionary mapping endpoint paths to average latency in milliseconds.
    """
    endpoint_times: dict[str, list[int]] = {}
    for api in apis:
        endpoint_times.setdefault(api.endpoint, []).append(api.duration_ms)
    
    return {
        endpoint: sum(times) / len(times)
        for endpoint, times in endpoint_times.items()
    }


def transform_active_sessions(users: list[UserEntry]) -> dict[str, str]:
    """
    Determine currently active sessions from user log entries.
    
    Args:
        users: List of UserEntry objects.
        
    Returns:
        A dictionary mapping user IDs to their login datetime (active sessions).
    """
    sessions: dict[str, str] = {}
    for user in users:
        if "logged in" in user.action:
            sessions[user.user_id] = user.datetime
        elif "logged out" in user.action and user.user_id in sessions:
            del sessions[user.user_id]
    return sessions


# =============================================================================
# Database Loading
# =============================================================================

def init_database(conn: sqlite3.Connection) -> None:
    """
    Initialize the database schema.
    
    Creates the required tables if they don't exist.
    
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


def load_errors(conn: sqlite3.Connection, errors_by_message: dict[str, int]) -> None:
    """
    Load error metrics into the database using parameterized queries.
    
    Args:
        conn: SQLite database connection.
        errors_by_message: Dictionary mapping error messages to counts.
    """
    cursor = conn.cursor()
    now = datetime.datetime.now().isoformat()
    
    for message, count in errors_by_message.items():
        # Parameterized query prevents SQL injection
        cursor.execute(
            "INSERT INTO errors (dt, message, count) VALUES (?, ?, ?)",
            (now, message, count)
        )
    conn.commit()


def load_api_metrics(conn: sqlite3.Connection, api_metrics: dict[str, float]) -> None:
    """
    Load API latency metrics into the database using parameterized queries.
    
    Args:
        conn: SQLite database connection.
        api_metrics: Dictionary mapping endpoints to average latency.
    """
    cursor = conn.cursor()
    now = datetime.datetime.now().isoformat()
    
    for endpoint, avg_ms in api_metrics.items():
        # Parameterized query prevents SQL injection
        cursor.execute(
            "INSERT INTO api_metrics (dt, endpoint, avg_ms) VALUES (?, ?, ?)",
            (now, endpoint, avg_ms)
        )
    conn.commit()


# =============================================================================
# Report Generation
# =============================================================================

def generate_report(
    errors_by_message: dict[str, int],
    api_metrics: dict[str, float],
    active_sessions: dict[str, str]
) -> str:
    """
    Generate an HTML report with error summary, API latency, and active sessions.
    
    Args:
        errors_by_message: Dictionary mapping error messages to counts.
        api_metrics: Dictionary mapping endpoints to average latency.
        active_sessions: Dictionary of currently active user sessions.
        
    Returns:
        HTML report as a string.
    """
    report = [
        "<html>",
        "<head><title>System Report</title></head>",
        "<body>",
        "<h1>Error Summary</h1>",
        "<ul>",
    ]
    
    for msg, count in errors_by_message.items():
        report.append(f"<li><b>{msg}</b>: {count} occurrences</li>")
    
    report.extend([
        "</ul>",
        "<h2>API Latency</h2>",
        "<table border='1'>",
        "<tr><th>Endpoint</th><th>Avg (ms)</th></tr>",
    ])
    
    for endpoint, avg in api_metrics.items():
        report.append(f"<tr><td>{endpoint}</td><td>{round(avg, 1)}</td></tr>")
    
    report.extend([
        "</table>",
        f"<h2>Active Sessions</h2>",
        f"<p>{len(active_sessions)} user(s) currently active</p>",
        "</body>",
        "</html>",
    ])
    
    return "\n".join(report)


# =============================================================================
# Main ETL Pipeline
# =============================================================================

def proc_data() -> None:
    """
    Main ETL pipeline function.
    
    1. Extract: Read and parse log file
    2. Transform: Aggregate metrics
    3. Load: Store in database
    4. Generate: Create HTML report
    """
    print(f"Connecting to {config.db_host}:{config.db_port} as {config.db_user}...")
    
    # EXTRACT
    errors, apis, users, warns = extract_logs(config.log_file)
    
    # TRANSFORM
    errors_by_message = transform_errors(errors)
    api_metrics = transform_api_metrics(apis)
    active_sessions = transform_active_sessions(users)
    
    # LOAD
    conn = sqlite3.connect(config.db_path)
    try:
        init_database(conn)
        load_errors(conn, errors_by_message)
        load_api_metrics(conn, api_metrics)
    finally:
        conn.close()
    
    # GENERATE REPORT
    report = generate_report(errors_by_message, api_metrics, active_sessions)
    output_path = "report.html"
    
    with open(output_path, "w") as f:
        f.write(report)
    
    print(f"Job finished at {datetime.datetime.now()}")


if __name__ == "__main__":
    if not os.path.exists(config.log_file):
        with open(config.log_file, "w") as f:
            f.write("2024-01-01 12:00:00 INFO User 42 logged in\n")
            f.write("2024-01-01 12:05:00 ERROR Database timeout\n")
            f.write("2024-01-01 12:05:05 ERROR Database timeout\n")
            f.write("2024-01-01 12:08:00 INFO API /users/profile took 250ms\n")
            f.write("2024-01-01 12:09:00 WARN Memory usage at 87%\n")
            f.write("2024-01-01 12:10:00 INFO User 42 logged out\n")
    
    proc_data()
