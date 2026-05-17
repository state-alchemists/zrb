"""Log processing pipeline with ETL pattern.

Extracts log entries from file, transforms them into metrics,
loads into SQLite database, and generates HTML report.
"""

import os
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List


# Configuration from environment variables
DB_PATH = os.getenv("DB_PATH", "metrics.db")
LOG_FILE = os.getenv("LOG_FILE", "server.log")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_USER = os.getenv("DB_USER", "admin")
DB_PASS = os.getenv("DB_PASS", "password123")


@dataclass(frozen=True, slots=True)
class LogEntry:
    """Represents a parsed log entry."""
    timestamp: str
    level: str
    message: str
    user_id: str | None = None
    action: str | None = None
    endpoint: str | None = None
    duration_ms: int | None = None


def extract_log_entries(log_path: Path) -> List[LogEntry]:
    """Extract and parse log entries from file.

    Args:
        log_path: Path to the log file.

    Returns:
        List of parsed log entries.
    """
    if not log_path.exists():
        return []

    entries: List[LogEntry] = []

    # Regex patterns for different log types
    error_pattern = re.compile(
        r'^(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) ERROR (?P<message>.+)$'
    )
    user_pattern = re.compile(
        r'^(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) INFO User (?P<user_id>\d+) (?P<action>.+)$'
    )
    api_pattern = re.compile(
        r'^(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) INFO API (?P<endpoint>\S+) took (?P<duration>\d+)ms$'
    )
    warn_pattern = re.compile(
        r'^(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) WARN (?P<message>.+)$'
    )

    with log_path.open("r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            # Try each pattern
            if match := error_pattern.match(line):
                entries.append(LogEntry(
                    timestamp=match.group("timestamp"),
                    level="ERROR",
                    message=match.group("message")
                ))
            elif match := user_pattern.match(line):
                entries.append(LogEntry(
                    timestamp=match.group("timestamp"),
                    level="INFO",
                    message=f"User {match.group('user_id')} {match.group('action')}",
                    user_id=match.group("user_id"),
                    action=match.group("action")
                ))
            elif match := api_pattern.match(line):
                entries.append(LogEntry(
                    timestamp=match.group("timestamp"),
                    level="INFO",
                    message=f"API {match.group('endpoint')} took {match.group('duration')}ms",
                    endpoint=match.group("endpoint"),
                    duration_ms=int(match.group("duration"))
                ))
            elif match := warn_pattern.match(line):
                entries.append(LogEntry(
                    timestamp=match.group("timestamp"),
                    level="WARN",
                    message=match.group("message")
                ))

    return entries


def transform_data(entries: List[LogEntry]) -> tuple[
    Dict[str, int],
    Dict[str, List[int]],
    Dict[str, str]
]:
    """Transform log entries into aggregated metrics.

    Args:
        entries: List of parsed log entries.

    Returns:
        Tuple of (error_counts, api_metrics, active_sessions).
    """
    error_counts: Dict[str, int] = {}
    api_metrics: Dict[str, List[int]] = {}
    active_sessions: Dict[str, str] = {}

    for entry in entries:
        if entry.level == "ERROR":
            error_counts[entry.message] = error_counts.get(entry.message, 0) + 1

        elif entry.level == "INFO" and entry.endpoint:
            api_metrics.setdefault(entry.endpoint, []).append(entry.duration_ms or 0)

        elif entry.level == "INFO" and entry.user_id and entry.action:
            if "logged in" in entry.action:
                active_sessions[entry.user_id] = entry.timestamp
            elif "logged out" in entry.action and entry.user_id in active_sessions:
                del active_sessions[entry.user_id]

    return error_counts, api_metrics, active_sessions


def load_metrics(
    db_path: str,
    error_counts: Dict[str, int],
    api_metrics: Dict[str, List[int]]
) -> None:
    """Load metrics into SQLite database.

    Args:
        db_path: Path to SQLite database.
        error_counts: Dictionary of error messages to counts.
        api_metrics: Dictionary of endpoints to latency lists.
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

    # Insert error counts with parameterized queries
    now = datetime.now()
    for message, count in error_counts.items():
        cursor.execute(
            "INSERT INTO errors VALUES (?, ?, ?)",
            (now.isoformat(), message, count)
        )

    # Insert API metrics with parameterized queries
    for endpoint, latencies in api_metrics.items():
        avg_ms = sum(latencies) / len(latencies)
        cursor.execute(
            "INSERT INTO api_metrics VALUES (?, ?, ?)",
            (now.isoformat(), endpoint, avg_ms)
        )

    conn.commit()
    conn.close()


def generate_report(
    error_counts: Dict[str, int],
    api_metrics: Dict[str, List[int]],
    active_sessions: Dict[str, str],
    output_path: str = "report.html"
) -> None:
    """Generate HTML report from metrics.

    Args:
        error_counts: Dictionary of error messages to counts.
        api_metrics: Dictionary of endpoints to latency lists.
        active_sessions: Dictionary of user IDs to login timestamps.
        output_path: Path for output HTML file.
    """
    lines = [
        "<html>",
        "<head><title>System Report</title></head>",
        "<body>",
        "<h1>Error Summary</h1>",
        "<ul>"
    ]

    for message, count in error_counts.items():
        lines.append(f"<li><b>{message}</b>: {count} occurrences</li>")

    lines.extend([
        "</ul>",
        "<h2>API Latency</h2>",
        "<table border='1'>",
        "<tr><th>Endpoint</th><th>Avg (ms)</th></tr>"
    ])

    for endpoint, latencies in api_metrics.items():
        avg_ms = sum(latencies) / len(latencies)
        lines.append(f"<tr><td>{endpoint}</td><td>{round(avg_ms, 1)}</td></tr>")

    lines.extend([
        "</table>",
        "<h2>Active Sessions</h2>",
        f"<p>{len(active_sessions)} user(s) currently active</p>",
        "</body>",
        "</html>"
    ])

    Path(output_path).write_text("\n".join(lines))


def main() -> None:
    """Main pipeline execution."""
    log_path = Path(LOG_FILE)

    # Extract
    entries = extract_log_entries(log_path)

    # Transform
    error_counts, api_metrics, active_sessions = transform_data(entries)

    # Load
    load_metrics(DB_PATH, error_counts, api_metrics)

    # Generate report
    generate_report(error_counts, api_metrics, active_sessions)

    print(f"Job finished at {datetime.now()}")


if __name__ == "__main__":
    # Create sample log file if it doesn't exist
    if not Path(LOG_FILE).exists():
        Path(LOG_FILE).write_text(
            "2024-01-01 12:00:00 INFO User 42 logged in\n"
            "2024-01-01 12:05:00 ERROR Database timeout\n"
            "2024-01-01 12:05:05 ERROR Database timeout\n"
            "2024-01-01 12:08:00 INFO API /users/profile took 250ms\n"
            "2024-01-01 12:09:00 WARN Memory usage at 87%\n"
            "2024-01-01 12:10:00 INFO User 42 logged out\n"
        )

    main()