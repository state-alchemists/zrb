"""
Server Log Processing Pipeline

Extracts metrics from server logs, aggregates them, and generates reports.
Follows ETL (Extract → Transform → Load) pattern for maintainability.

Environment Variables:
    DB_PATH: Path to SQLite database (default: metrics.db)
    LOG_FILE: Path to server log file (default: server.log)
    DB_HOST: Database host (default: localhost)
    DB_PORT: Database port (default: 5432)
    DB_USER: Database user (default: admin)
    DB_PASS: Database password (default: password123)
"""

import os
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional


# Configuration from environment variables with defaults
DB_PATH = os.getenv("DB_PATH", "metrics.db")
LOG_FILE = os.getenv("LOG_FILE", "server.log")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_USER = os.getenv("DB_USER", "admin")
DB_PASS = os.getenv("DB_PASS", "password123")


@dataclass
class LogEntry:
    """Represents a parsed log entry."""
    timestamp: str
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
    """API performance metric."""
    endpoint: str
    avg_ms: float


# Regex patterns for log parsing
LOG_PATTERNS = {
    "error": re.compile(
        r'^(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) ERROR (?P<message>.+)$'
    ),
    "user": re.compile(
        r'^(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) INFO User (?P<user_id>\d+) (?P<action>.+)$'
    ),
    "api": re.compile(
        r'^(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) INFO API (?P<endpoint>\S+)(?: took (?P<duration>\d+)ms)?$'
    ),
    "warn": re.compile(
        r'^(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) WARN (?P<message>.+)$'
    ),
}


def extract_log_entries(log_file_path: str) -> List[LogEntry]:
    """
    Extract and parse log entries from the log file.

    Args:
        log_file_path: Path to the log file.

    Returns:
        List of parsed LogEntry objects.
    """
    entries: List[LogEntry] = []

    if not os.path.exists(log_file_path):
        return entries

    with open(log_file_path, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            # Try each pattern
            for pattern_name, pattern in LOG_PATTERNS.items():
                match = pattern.match(line)
                if match:
                    groups = match.groupdict()
                    timestamp = groups["timestamp"]

                    if pattern_name == "error":
                        entries.append(LogEntry(
                            timestamp=timestamp,
                            level="ERROR",
                            message=groups["message"]
                        ))
                    elif pattern_name == "user":
                        entries.append(LogEntry(
                            timestamp=timestamp,
                            level="INFO",
                            message=f"User {groups['user_id']} {groups['action']}",
                            user_id=groups["user_id"],
                            action=groups["action"]
                        ))
                    elif pattern_name == "api":
                        duration = int(groups["duration"]) if groups.get("duration") else None
                        entries.append(LogEntry(
                            timestamp=timestamp,
                            level="INFO",
                            message=f"API {groups['endpoint']}",
                            endpoint=groups["endpoint"],
                            duration_ms=duration
                        ))
                    elif pattern_name == "warn":
                        entries.append(LogEntry(
                            timestamp=timestamp,
                            level="WARN",
                            message=groups["message"]
                        ))
                    break

    return entries


def transform_entries(
    entries: List[LogEntry]
) -> tuple[Dict[str, int], Dict[str, List[int]], Dict[str, str]]:
    """
    Transform log entries into aggregated metrics.

    Args:
        entries: List of parsed log entries.

    Returns:
        Tuple of:
        - Error message counts (message -> count)
        - API endpoint latencies (endpoint -> list of durations)
        - Active sessions (user_id -> login timestamp)
    """
    error_counts: Dict[str, int] = {}
    api_latencies: Dict[str, List[int]] = {}
    active_sessions: Dict[str, str] = {}

    for entry in entries:
        # Count errors
        if entry.level == "ERROR":
            error_counts[entry.message] = error_counts.get(entry.message, 0) + 1

        # Track API latencies
        if entry.endpoint and entry.duration_ms is not None:
            api_latencies.setdefault(entry.endpoint, []).append(entry.duration_ms)

        # Track active sessions
        if entry.user_id and entry.action:
            if "logged in" in entry.action:
                active_sessions[entry.user_id] = entry.timestamp
            elif "logged out" in entry.action and entry.user_id in active_sessions:
                del active_sessions[entry.user_id]

    return error_counts, api_latencies, active_sessions


def load_to_database(
    db_path: str,
    error_counts: Dict[str, int],
    api_latencies: Dict[str, List[int]]
) -> None:
    """
    Load aggregated metrics into the database.

    Uses parameterized queries to prevent SQL injection.

    Args:
        db_path: Path to SQLite database.
        error_counts: Error message counts.
        api_latencies: API endpoint latencies.
    """
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

    # Insert error counts with parameterized query
    now = datetime.now()
    for message, count in error_counts.items():
        cursor.execute(
            "INSERT INTO errors (dt, message, count) VALUES (?, ?, ?)",
            (now, message, count)
        )

    # Insert API metrics with parameterized query
    for endpoint, durations in api_latencies.items():
        avg_ms = sum(durations) / len(durations)
        cursor.execute(
            "INSERT INTO api_metrics (dt, endpoint, avg_ms) VALUES (?, ?, ?)",
            (now, endpoint, avg_ms)
        )

    conn.commit()
    conn.close()


def generate_html_report(
    error_counts: Dict[str, int],
    api_latencies: Dict[str, List[int]],
    active_sessions: Dict[str, str],
    output_path: str = "report.html"
) -> None:
    """
    Generate HTML report from aggregated metrics.

    Args:
        error_counts: Error message counts.
        api_latencies: API endpoint latencies.
        active_sessions: Active user sessions.
        output_path: Path for output HTML file.
    """
    lines = [
        "<html>",
        "<head><title>System Report</title></head>",
        "<body>",
        "<h1>Error Summary</h1>",
        "<ul>",
    ]

    for err_msg, count in error_counts.items():
        lines.append(f"<li><b>{err_msg}</b>: {count} occurrences</li>")

    lines.extend([
        "</ul>",
        "<h2>API Latency</h2>",
        "<table border='1'>",
        "<tr><th>Endpoint</th><th>Avg (ms)</th></tr>",
    ])

    for endpoint, durations in api_latencies.items():
        avg = sum(durations) / len(durations)
        lines.append(f"<tr><td>{endpoint}</td><td>{round(avg, 1)}</td></tr>")

    lines.extend([
        "</table>",
        "<h2>Active Sessions</h2>",
        f"<p>{len(active_sessions)} user(s) currently active</p>",
        "</body>",
        "</html>",
    ])

    with open(output_path, "w") as f:
        f.write("\n".join(lines))


def main() -> None:
    """Main pipeline execution: Extract → Transform → Load."""
    print(f"Connecting to {DB_HOST}:{DB_PORT} as {DB_USER}...")

    # Extract
    entries = extract_log_entries(LOG_FILE)
    print(f"Parsed {len(entries)} log entries from {LOG_FILE}")

    # Transform
    error_counts, api_latencies, active_sessions = transform_entries(entries)
    print(f"Found {len(error_counts)} unique errors")
    print(f"Tracked {len(api_latencies)} API endpoints")
    print(f"Active sessions: {len(active_sessions)}")

    # Load to database
    load_to_database(DB_PATH, error_counts, api_latencies)

    # Generate report
    generate_html_report(error_counts, api_latencies, active_sessions)

    print(f"Job finished at {datetime.now()}")


if __name__ == "__main__":
    # Create sample log file if it doesn't exist
    if not os.path.exists(LOG_FILE):
        with open(LOG_FILE, "w") as f:
            f.write("2024-01-01 12:00:00 INFO User 42 logged in\n")
            f.write("2024-01-01 12:05:00 ERROR Database timeout\n")
            f.write("2024-01-01 12:05:05 ERROR Database timeout\n")
            f.write("2024-01-01 12:08:00 INFO API /users/profile took 250ms\n")
            f.write("2024-01-01 12:09:00 WARN Memory usage at 87%\n")
            f.write("2024-01-01 12:10:00 INFO User 42 logged out\n")

    main()