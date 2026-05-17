"""
Server Log Processing Pipeline (Refactored)

Extracts data from server logs, transforms metrics, loads into SQLite,
and generates an HTML report.
"""

import datetime
import os
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple


# =============================================================================
# Configuration (loaded from environment variables)
# =============================================================================

ENV_PREFIX = "LOGPIPELINE_"


def get_config() -> Dict[str, str]:
    """
    Load configuration from environment variables.
    
    Falls back to reasonable defaults for local development,
    but requires explicit DB credentials via env vars.
    
    Returns:
        Dictionary containing configuration values.
        
    Raises:
        ValueError: If required credentials are not provided.
    """
    config = {
        "db_path": os.getenv(f"{ENV_PREFIX}DB_PATH", "metrics.db"),
        "log_file": os.getenv(f"{ENV_PREFIX}LOG_FILE", "server.log"),
        "db_host": os.getenv(f"{ENV_PREFIX}DB_HOST", "localhost"),
        "db_port": os.getenv(f"{ENV_PREFIX}DB_PORT", "5432"),
        "db_user": os.getenv(f"{ENV_PREFIX}DB_USER"),
        "db_pass": os.getenv(f"{ENV_PREFIX}DB_PASS"),
    }
    
    if not config["db_user"] or not config["db_pass"]:
        raise ValueError(
            f"Database credentials required via "
            f"{ENV_PREFIX}DB_USER and {ENV_PREFIX}DB_PASS environment variables"
        )
    
    return config


# =============================================================================
# Data Classes
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
class UserEntry(LogEntry):
    """Represents a user action log entry."""
    user_id: str
    action: str


@dataclass
class ApiEntry(LogEntry):
    """Represents an API call log entry."""
    endpoint: str
    duration_ms: int


@dataclass
class WarnEntry(LogEntry):
    """Represents a warning log entry."""
    message: str


# Union type for all entry types
LogEntryType = Optional[ErrorEntry | UserEntry | ApiEntry | WarnEntry]


# =============================================================================
# Log Parsing (Extract Phase)
# =============================================================================

# Regex patterns for parsing log lines
LOG_LINE_PATTERN = re.compile(
    r"^(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2}:\d{2})\s+(\w+)\s+(.*)$"
)

USER_ACTION_PATTERN = re.compile(
    r"User\s+(\w+)\s+(.+)"
)

API_CALL_PATTERN = re.compile(
    r"API\s+(\S+)\s+took\s+(\d+)ms"
)


def parse_log_line(line: str) -> LogEntryType:
    """
    Parse a single log line into a typed entry.
    
    Expected format: "YYYY-MM-DD HH:MM:SS LEVEL message..."
    
    Args:
        line: Raw log line string.
        
    Returns:
        Typed LogEntry subclass or None if line doesn't match expected format.
    """
    match = LOG_LINE_PATTERN.match(line.strip())
    if not match:
        return None
    
    date_part, time_part, level, message = match.groups()
    timestamp = f"{date_part} {time_part}"
    level = level.upper()
    
    if level == "ERROR":
        return ErrorEntry(timestamp=timestamp, level=level, message=message)
    
    if level == "WARN":
        return WarnEntry(timestamp=timestamp, level=level, message=message)
    
    if level == "INFO":
        # Check for user action
        user_match = USER_ACTION_PATTERN.match(message)
        if user_match:
            user_id, action = user_match.groups()
            return UserEntry(
                timestamp=timestamp,
                level=level,
                user_id=user_id,
                action=action
            )
        
        # Check for API call
        api_match = API_CALL_PATTERN.match(message)
        if api_match:
            endpoint, duration = api_match.groups()
            return ApiEntry(
                timestamp=timestamp,
                level=level,
                endpoint=endpoint,
                duration_ms=int(duration)
            )
    
    return None


def extract_log_data(log_path: str) -> Tuple[List[ErrorEntry], List[ApiEntry], List[UserEntry], List[WarnEntry]]:
    """
    Extract and categorize data from the log file.
    
    Args:
        log_path: Path to the log file.
        
    Returns:
        Tuple of (errors, api_calls, user_actions, warnings) lists.
    """
    errors: List[ErrorEntry] = []
    api_calls: List[ApiEntry] = []
    user_actions: List[UserEntry] = []
    warnings: List[WarnEntry] = []
    
    if not os.path.exists(log_path):
        return errors, api_calls, user_actions, warnings
    
    with open(log_path, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            entry = parse_log_line(line)
            
            if isinstance(entry, ErrorEntry):
                errors.append(entry)
            elif isinstance(entry, ApiEntry):
                api_calls.append(entry)
            elif isinstance(entry, UserEntry):
                user_actions.append(entry)
            elif isinstance(entry, WarnEntry):
                warnings.append(entry)
    
    return errors, api_calls, user_actions, warnings


# =============================================================================
# Data Transformation (Transform Phase)
# =============================================================================

def transform_error_summary(errors: List[ErrorEntry]) -> Dict[str, int]:
    """
    Aggregate errors by message for summary reporting.
    
    Args:
        errors: List of error entries.
        
    Returns:
        Dictionary mapping error message to occurrence count.
    """
    summary: Dict[str, int] = {}
    for error in errors:
        summary[error.message] = summary.get(error.message, 0) + 1
    return summary


def transform_api_latency(api_calls: List[ApiEntry]) -> Dict[str, Dict[str, float]]:
    """
    Calculate average latency per API endpoint.
    
    Args:
        api_calls: List of API call entries.
        
    Returns:
        Dictionary mapping endpoint to stats dict with 'count' and 'avg_ms'.
    """
    endpoint_stats: Dict[str, List[int]] = {}
    
    for call in api_calls:
        if call.endpoint not in endpoint_stats:
            endpoint_stats[call.endpoint] = []
        endpoint_stats[call.endpoint].append(call.duration_ms)
    
    result: Dict[str, Dict[str, float]] = {}
    for endpoint, durations in endpoint_stats.items():
        result[endpoint] = {
            "count": len(durations),
            "avg_ms": sum(durations) / len(durations)
        }
    
    return result


def transform_active_sessions(user_actions: List[UserEntry]) -> Dict[str, str]:
    """
    Track active user sessions based on login/logout actions.
    
    Args:
        user_actions: List of user action entries.
        
    Returns:
        Dictionary mapping active user_id to login timestamp.
    """
    sessions: Dict[str, str] = {}
    
    for action in user_actions:
        if "logged in" in action.action.lower():
            sessions[action.user_id] = action.timestamp
        elif "logged out" in action.action.lower() and action.user_id in sessions:
            del sessions[action.user_id]
    
    return sessions


# =============================================================================
# Database Operations (Load Phase)
# =============================================================================

def init_database(db_path: str, db_host: str, db_port: str, db_user: str, db_pass: str) -> sqlite3.Connection:
    """
    Initialize database connection and schema.
    
    Args:
        db_path: Path to SQLite database file.
        db_host: Database host (for display/logging purposes).
        db_port: Database port (for display/logging purposes).
        db_user: Database username.
        db_pass: Database password.
        
    Returns:
        SQLite connection object.
    """
    print(f"Connecting to {db_host}:{db_port} as {db_user}...")
    
    conn = sqlite3.connect(db_path)
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


def load_error_metrics(
    conn: sqlite3.Connection,
    error_summary: Dict[str, int]
) -> None:
    """
    Load error summary data into the database using parameterized queries.
    
    Args:
        conn: Database connection.
        error_summary: Dictionary of error messages to counts.
    """
    cursor = conn.cursor()
    now = datetime.datetime.now().isoformat()
    
    for msg, count in error_summary.items():
        cursor.execute(
            "INSERT INTO errors (dt, message, count) VALUES (?, ?, ?)",
            (now, msg, count)
        )
    
    conn.commit()


def load_api_metrics(
    conn: sqlite3.Connection,
    api_stats: Dict[str, Dict[str, float]]
) -> None:
    """
    Load API latency metrics into the database using parameterized queries.
    
    Args:
        conn: Database connection.
        api_stats: Dictionary of endpoint to latency statistics.
    """
    cursor = conn.cursor()
    now = datetime.datetime.now().isoformat()
    
    for endpoint, stats in api_stats.items():
        cursor.execute(
            "INSERT INTO api_metrics (dt, endpoint, avg_ms) VALUES (?, ?, ?)",
            (now, endpoint, stats["avg_ms"])
        )
    
    conn.commit()


def close_database(conn: sqlite3.Connection) -> None:
    """Safely close the database connection."""
    conn.close()


# =============================================================================
# Report Generation
# =============================================================================

def generate_html_report(
    error_summary: Dict[str, int],
    api_stats: Dict[str, Dict[str, float]],
    active_sessions: Dict[str, str],
    output_path: str = "report.html"
) -> None:
    """
    Generate an HTML report from processed data.
    
    Args:
        error_summary: Dictionary of error messages to counts.
        api_stats: Dictionary of API endpoint latency statistics.
        active_sessions: Dictionary of active user sessions.
        output_path: Path for the output HTML file.
    """
    html_parts: List[str] = [
        "<html>",
        "<head><title>System Report</title></head>",
        "<body>",
        "<h1>Error Summary</h1>",
        "<ul>"
    ]
    
    for err_msg, count in error_summary.items():
        escaped_msg = err_msg.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        html_parts.append(f"<li><b>{escaped_msg}</b>: {count} occurrences</li>")
    
    html_parts.extend([
        "</ul>",
        "<h2>API Latency</h2>",
        "<table border='1'>",
        "<tr><th>Endpoint</th><th>Avg (ms)</th></tr>"
    ])
    
    for ep, stats in api_stats.items():
        avg = round(stats["avg_ms"], 1)
        html_parts.append(f"<tr><td>{ep}</td><td>{avg}</td></tr>")
    
    html_parts.extend([
        "</table>",
        "<h2>Active Sessions</h2>",
        f"<p>{len(active_sessions)} user(s) currently active</p>",
        "</body>",
        "</html>"
    ])
    
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(html_parts))


# =============================================================================
# Main Pipeline Orchestration
# =============================================================================

def run_pipeline() -> None:
    """
    Execute the full ETL pipeline.
    
    Steps:
        1. Load configuration from environment
        2. Extract: Parse log file
        3. Transform: Aggregate metrics
        4. Load: Store in database
        5. Generate HTML report
    """
    config = get_config()
    
    # Extract
    errors, api_calls, user_actions, warnings = extract_log_data(config["log_file"])
    
    # Transform
    error_summary = transform_error_summary(errors)
    api_stats = transform_api_latency(api_calls)
    active_sessions = transform_active_sessions(user_actions)
    
    # Load
    conn = init_database(
        config["db_path"],
        config["db_host"],
        config["db_port"],
        config["db_user"],
        config["db_pass"]
    )
    try:
        load_error_metrics(conn, error_summary)
        load_api_metrics(conn, api_stats)
    finally:
        close_database(conn)
    
    # Report
    generate_html_report(error_summary, api_stats, active_sessions)
    
    print(f"Job finished at {datetime.datetime.now()}")


def create_sample_log_file(log_path: str) -> None:
    """
    Create a sample log file for testing if one doesn't exist.
    
    Args:
        log_path: Path where the sample log should be written.
    """
    sample_lines = [
        "2024-01-01 12:00:00 INFO User 42 logged in\n",
        "2024-01-01 12:05:00 ERROR Database timeout\n",
        "2024-01-01 12:05:05 ERROR Database timeout\n",
        "2024-01-01 12:08:00 INFO API /users/profile took 250ms\n",
        "2024-01-01 12:09:00 WARN Memory usage at 87%\n",
        "2024-01-01 12:10:00 INFO User 42 logged out\n"
    ]
    
    with open(log_path, "w", encoding="utf-8") as f:
        f.writelines(sample_lines)


# =============================================================================
# Entry Point
# =============================================================================

if __name__ == "__main__":
    config = get_config()
    
    if not os.path.exists(config["log_file"]):
        create_sample_log_file(config["log_file"])
    
    run_pipeline()
