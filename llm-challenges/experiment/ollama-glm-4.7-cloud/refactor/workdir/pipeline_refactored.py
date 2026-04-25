"""
Log processing pipeline for server metrics.

This script processes server logs, aggregates metrics, and generates reports.
Follows Extract-Transform-Load (ETL) pattern with proper security practices.
"""

import os
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional


# Configuration from environment variables
DB_PATH = os.getenv("DB_PATH", "metrics.db")
LOG_FILE = os.getenv("LOG_FILE", "server.log")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_USER = os.getenv("DB_USER", "admin")
DB_PASS = os.getenv("DB_PASS", "password123")
REPORT_OUTPUT = os.getenv("REPORT_OUTPUT", "report.html")


@dataclass
class LogEntry:
    """Represents a parsed log entry."""
    timestamp: datetime
    level: str
    message: str
    user_id: Optional[str] = None
    action: Optional[str] = None
    endpoint: Optional[str] = None
    duration_ms: Optional[int] = None


@dataclass
class ErrorSummary:
    """Aggregated error statistics."""
    message: str
    count: int


@dataclass
class ApiMetric:
    """Aggregated API performance metrics."""
    endpoint: str
    avg_ms: float
    call_count: int


@dataclass
class ReportData:
    """Container for all report data."""
    error_summaries: List[ErrorSummary]
    api_metrics: List[ApiMetric]
    active_session_count: int


# ============================================================================
# EXTRACT PHASE
# ============================================================================

def parse_log_line(line: str) -> Optional[LogEntry]:
    """
    Parse a single log line into a structured LogEntry.

    Expected format: YYYY-MM-DD HH:MM:SS LEVEL message

    Args:
        line: Raw log line string

    Returns:
        LogEntry if parsing succeeds, None otherwise
    """
    # Pattern: timestamp, level, and rest of message
    pattern = r'^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) (\w+) (.+)$'
    match = re.match(pattern, line.strip())

    if not match:
        return None

    timestamp_str, level, message = match.groups()

    try:
        timestamp = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None

    entry = LogEntry(
        timestamp=timestamp,
        level=level,
        message=message
    )

    # Parse user actions
    if level == "INFO" and "User" in message:
        user_match = re.search(r'User (\d+) (.+)', message)
        if user_match:
            entry.user_id = user_match.group(1)
            entry.action = user_match.group(2)

    # Parse API calls
    elif level == "INFO" and "API" in message:
        api_match = re.search(r'API (\S+) took (\d+)ms', message)
        if api_match:
            entry.endpoint = api_match.group(1)
            entry.duration_ms = int(api_match.group(2))

    return entry


def extract_log_entries(log_file_path: str) -> List[LogEntry]:
    """
    Extract and parse all log entries from the log file.

    Args:
        log_file_path: Path to the log file

    Returns:
        List of parsed LogEntry objects
    """
    entries = []

    if not os.path.exists(log_file_path):
        print(f"Warning: Log file not found: {log_file_path}")
        return entries

    with open(log_file_path, "r") as f:
        for line in f:
            entry = parse_log_line(line)
            if entry:
                entries.append(entry)

    return entries


# ============================================================================
# TRANSFORM PHASE
# ============================================================================

def aggregate_errors(entries: List[LogEntry]) -> List[ErrorSummary]:
    """
    Aggregate error messages by occurrence count.

    Args:
        entries: List of parsed log entries

    Returns:
        List of ErrorSummary objects sorted by count (descending)
    """
    error_counts: Dict[str, int] = {}

    for entry in entries:
        if entry.level == "ERROR":
            error_counts[entry.message] = error_counts.get(entry.message, 0) + 1

    summaries = [
        ErrorSummary(message=msg, count=count)
        for msg, count in error_counts.items()
    ]

    # Sort by count descending
    summaries.sort(key=lambda x: x.count, reverse=True)
    return summaries


def aggregate_api_metrics(entries: List[LogEntry]) -> List[ApiMetric]:
    """
    Aggregate API call metrics by endpoint.

    Args:
        entries: List of parsed log entries

    Returns:
        List of ApiMetric objects
    """
    endpoint_times: Dict[str, List[int]] = {}

    for entry in entries:
        if entry.endpoint and entry.duration_ms is not None:
            endpoint_times.setdefault(entry.endpoint, []).append(entry.duration_ms)

    metrics = []
    for endpoint, times in endpoint_times.items():
        avg_ms = sum(times) / len(times)
        metrics.append(ApiMetric(
            endpoint=endpoint,
            avg_ms=avg_ms,
            call_count=len(times)
        ))

    # Sort by average latency descending
    metrics.sort(key=lambda x: x.avg_ms, reverse=True)
    return metrics


def calculate_active_sessions(entries: List[LogEntry]) -> int:
    """
    Calculate currently active user sessions.

    A session is active if a user logged in but hasn't logged out.

    Args:
        entries: List of parsed log entries

    Returns:
        Number of active sessions
    """
    active_sessions: Dict[str, datetime] = {}

    for entry in entries:
        if entry.user_id and entry.action:
            if "logged in" in entry.action:
                active_sessions[entry.user_id] = entry.timestamp
            elif "logged out" in entry.action and entry.user_id in active_sessions:
                del active_sessions[entry.user_id]

    return len(active_sessions)


def transform_data(entries: List[LogEntry]) -> ReportData:
    """
    Transform raw log entries into aggregated report data.

    Args:
        entries: List of parsed log entries

    Returns:
        ReportData containing all aggregated metrics
    """
    error_summaries = aggregate_errors(entries)
    api_metrics = aggregate_api_metrics(entries)
    active_session_count = calculate_active_sessions(entries)

    return ReportData(
        error_summaries=error_summaries,
        api_metrics=api_metrics,
        active_session_count=active_session_count
    )


# ============================================================================
# LOAD PHASE
# ============================================================================

def create_database_schema(conn: sqlite3.Connection) -> None:
    """
    Create database tables if they don't exist.

    Args:
        conn: SQLite database connection
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


def store_error_summaries(
    conn: sqlite3.Connection,
    summaries: List[ErrorSummary]
) -> None:
    """
    Store error summaries in the database using parameterized queries.

    Args:
        conn: SQLite database connection
        summaries: List of ErrorSummary objects
    """
    cursor = conn.cursor()
    now = datetime.now()

    for summary in summaries:
        # Parameterized query - prevents SQL injection
        cursor.execute(
            "INSERT INTO errors (dt, message, count) VALUES (?, ?, ?)",
            (now.isoformat(), summary.message, summary.count)
        )


def store_api_metrics(
    conn: sqlite3.Connection,
    metrics: List[ApiMetric]
) -> None:
    """
    Store API metrics in the database using parameterized queries.

    Args:
        conn: SQLite database connection
        metrics: List of ApiMetric objects
    """
    cursor = conn.cursor()
    now = datetime.now()

    for metric in metrics:
        # Parameterized query - prevents SQL injection
        cursor.execute(
            "INSERT INTO api_metrics (dt, endpoint, avg_ms) VALUES (?, ?, ?)",
            (now.isoformat(), metric.endpoint, metric.avg_ms)
        )


def load_to_database(data: ReportData, db_path: str) -> None:
    """
    Load transformed data into the database.

    Args:
        data: ReportData containing aggregated metrics
        db_path: Path to SQLite database file
    """
    print(f"Connecting to database: {db_path}")

    conn = sqlite3.connect(db_path)
    create_database_schema(conn)

    store_error_summaries(conn, data.error_summaries)
    store_api_metrics(conn, data.api_metrics)

    conn.commit()
    conn.close()


def generate_html_report(data: ReportData, output_path: str) -> None:
    """
    Generate an HTML report from the aggregated data.

    Args:
        data: ReportData containing aggregated metrics
        output_path: Path where the HTML report will be written
    """
    html_parts = [
        "<html>",
        "<head><title>System Report</title></head>",
        "<body>",
        "<h1>Error Summary</h1>",
        "<ul>"
    ]

    for summary in data.error_summaries:
        html_parts.append(
            f"<li><b>{summary.message}</b>: {summary.count} occurrences</li>"
        )

    html_parts.extend([
        "</ul>",
        "<h2>API Latency</h2>",
        "<table border='1'>",
        "<tr><th>Endpoint</th><th>Avg (ms)</th></tr>"
    ])

    for metric in data.api_metrics:
        html_parts.append(
            f"<tr><td>{metric.endpoint}</td>"
            f"<td>{round(metric.avg_ms, 1)}</td></tr>"
        )

    html_parts.extend([
        "</table>",
        "<h2>Active Sessions</h2>",
        f"<p>{data.active_session_count} user(s) currently active</p>",
        "</body>",
        "</html>"
    ])

    html_content = "\n".join(html_parts)

    with open(output_path, "w") as f:
        f.write(html_content)


def load_report(data: ReportData, output_path: str) -> None:
    """
    Load report data to HTML file.

    Args:
        data: ReportData containing aggregated metrics
        output_path: Path where the HTML report will be written
    """
    generate_html_report(data, output_path)
    print(f"Report generated: {output_path}")


# ============================================================================
# MAIN PIPELINE
# ============================================================================

def run_pipeline() -> None:
    """
    Execute the complete ETL pipeline.

    Extract: Read and parse log file
    Transform: Aggregate metrics
    Load: Store in database and generate HTML report
    """
    print(f"Starting pipeline at {datetime.now()}")
    print(f"Log file: {LOG_FILE}")
    print(f"Database: {DB_PATH}")

    # Extract
    entries = extract_log_entries(LOG_FILE)
    print(f"Parsed {len(entries)} log entries")

    # Transform
    data = transform_data(entries)
    print(f"Found {len(data.error_summaries)} unique errors")
    print(f"Found {len(data.api_metrics)} API endpoints")
    print(f"Active sessions: {data.active_session_count}")

    # Load
    load_to_database(data, DB_PATH)
    load_report(data, REPORT_OUTPUT)

    print(f"Pipeline completed at {datetime.now()}")


def create_sample_log_file(log_file_path: str) -> None:
    """
    Create a sample log file for testing purposes.

    Args:
        log_file_path: Path where the sample log will be created
    """
    sample_lines = [
        "2024-01-01 12:00:00 INFO User 42 logged in",
        "2024-01-01 12:05:00 ERROR Database timeout",
        "2024-01-01 12:05:05 ERROR Database timeout",
        "2024-01-01 12:08:00 INFO API /users/profile took 250ms",
        "2024-01-01 12:09:00 WARN Memory usage at 87%",
        "2024-01-01 12:10:00 INFO User 42 logged out",
    ]

    with open(log_file_path, "w") as f:
        f.write("\n".join(sample_lines) + "\n")

    print(f"Created sample log file: {log_file_path}")


if __name__ == "__main__":
    # Create sample log if it doesn't exist
    if not os.path.exists(LOG_FILE):
        create_sample_log_file(LOG_FILE)

    run_pipeline()