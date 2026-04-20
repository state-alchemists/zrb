"""
Server log processing pipeline.

Extracts, transforms, and loads server log data into a database and generates
an HTML report with error summaries, API latency metrics, and active session counts.
"""

import os
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional


# ============================================================================
# Configuration
# ============================================================================

@dataclass
class Config:
    """Configuration loaded from environment variables."""
    db_path: str
    log_file: str
    db_host: str
    db_port: int
    db_user: str
    db_pass: str

    @classmethod
    def from_env(cls) -> "Config":
        """Load configuration from environment variables with defaults."""
        return cls(
            db_path=os.getenv("DB_PATH", "metrics.db"),
            log_file=os.getenv("LOG_FILE", "server.log"),
            db_host=os.getenv("DB_HOST", "localhost"),
            db_port=int(os.getenv("DB_PORT", "5432")),
            db_user=os.getenv("DB_USER", "admin"),
            db_pass=os.getenv("DB_PASS", "password123"),
        )


# ============================================================================
# Data Models
# ============================================================================

@dataclass
class LogEntry:
    """Base class for parsed log entries."""
    timestamp: datetime
    level: str


@dataclass
class ErrorEntry(LogEntry):
    """Represents an ERROR log entry."""
    message: str


@dataclass
class UserActionEntry(LogEntry):
    """Represents a user action (login/logout) log entry."""
    user_id: str
    action: str


@dataclass
class ApiCallEntry(LogEntry):
    """Represents an API call log entry."""
    endpoint: str
    duration_ms: int


@dataclass
class WarningEntry(LogEntry):
    """Represents a WARNING log entry."""
    message: str


# ============================================================================
# Extract: Log Parsing
# ============================================================================

def parse_log_line(line: str) -> Optional[LogEntry]:
    """
    Parse a single log line using regex.

    Args:
        line: Raw log line string.

    Returns:
        Parsed LogEntry subclass or None if line doesn't match expected format.
    """
    # Pattern: YYYY-MM-DD HH:MM:SS LEVEL message...
    pattern = r'^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) (\w+) (.+)$'
    match = re.match(pattern, line.strip())
    if not match:
        return None

    timestamp_str, level, message = match.groups()
    try:
        timestamp = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None

    if level == "ERROR":
        return ErrorEntry(timestamp=timestamp, level=level, message=message)
    elif level == "WARN":
        return WarningEntry(timestamp=timestamp, level=level, message=message)
    elif level == "INFO":
        # Parse user actions: "User {id} {action}"
        user_match = re.match(r'User (\d+) (.+)', message)
        if user_match:
            user_id, action = user_match.groups()
            return UserActionEntry(
                timestamp=timestamp, level=level, user_id=user_id, action=action
            )

        # Parse API calls: "API {endpoint} took {duration}ms"
        api_match = re.match(r'API (\S+) took (\d+)ms', message)
        if api_match:
            endpoint, duration = api_match.groups()
            return ApiCallEntry(
                timestamp=timestamp,
                level=level,
                endpoint=endpoint,
                duration_ms=int(duration),
            )

    return None


def extract_log_entries(log_file: str) -> List[LogEntry]:
    """
    Extract and parse all log entries from the log file.

    Args:
        log_file: Path to the log file.

    Returns:
        List of parsed LogEntry objects.
    """
    if not os.path.exists(log_file):
        return []

    entries: List[LogEntry] = []
    with open(log_file, "r") as f:
        for line in f:
            entry = parse_log_line(line)
            if entry:
                entries.append(entry)

    return entries


# ============================================================================
# Transform: Data Aggregation
# ============================================================================

@dataclass
class AggregatedMetrics:
    """Aggregated metrics from log data."""
    error_counts: Dict[str, int]
    api_latency: Dict[str, List[int]]
    active_sessions: Dict[str, datetime]


def transform_entries(entries: List[LogEntry]) -> AggregatedMetrics:
    """
    Transform parsed log entries into aggregated metrics.

    Args:
        entries: List of parsed LogEntry objects.

    Returns:
        AggregatedMetrics containing error counts, API latency data, and active sessions.
    """
    error_counts: Dict[str, int] = {}
    api_latency: Dict[str, List[int]] = {}
    active_sessions: Dict[str, datetime] = {}

    for entry in entries:
        if isinstance(entry, ErrorEntry):
            error_counts[entry.message] = error_counts.get(entry.message, 0) + 1

        elif isinstance(entry, ApiCallEntry):
            api_latency.setdefault(entry.endpoint, []).append(entry.duration_ms)

        elif isinstance(entry, UserActionEntry):
            if "logged in" in entry.action:
                active_sessions[entry.user_id] = entry.timestamp
            elif "logged out" in entry.action and entry.user_id in active_sessions:
                del active_sessions[entry.user_id]

    return AggregatedMetrics(
        error_counts=error_counts,
        api_latency=api_latency,
        active_sessions=active_sessions,
    )


# ============================================================================
# Load: Database Storage
# ============================================================================

def create_tables(cursor: sqlite3.Cursor) -> None:
    """Create database tables if they don't exist."""
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


def load_metrics_to_db(
    metrics: AggregatedMetrics,
    db_path: str,
    config: Config,
) -> None:
    """
    Load aggregated metrics into the database using parameterized queries.

    Args:
        metrics: Aggregated metrics to store.
        db_path: Path to the SQLite database.
        config: Configuration object (for logging connection info).
    """
    print(f"Connecting to {config.db_host}:{config.db_port} as {config.db_user}...")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    create_tables(cursor)

    # Insert error counts with parameterized query
    for message, count in metrics.error_counts.items():
        cursor.execute(
            "INSERT INTO errors (dt, message, count) VALUES (?, ?, ?)",
            (datetime.now().isoformat(), message, count),
        )

    # Insert API latency metrics with parameterized query
    for endpoint, durations in metrics.api_latency.items():
        avg_ms = sum(durations) / len(durations)
        cursor.execute(
            "INSERT INTO api_metrics (dt, endpoint, avg_ms) VALUES (?, ?, ?)",
            (datetime.now().isoformat(), endpoint, avg_ms),
        )

    conn.commit()
    conn.close()


# ============================================================================
# Report Generation
# ============================================================================

def generate_html_report(metrics: AggregatedMetrics, output_path: str) -> None:
    """
    Generate an HTML report from aggregated metrics.

    Args:
        metrics: Aggregated metrics to report on.
        output_path: Path where the HTML report will be written.
    """
    lines = [
        "<html>",
        "<head><title>System Report</title></head>",
        "<body>",
        "<h1>Error Summary</h1>",
        "<ul>",
    ]

    for err_msg, count in metrics.error_counts.items():
        lines.append(f"<li><b>{err_msg}</b>: {count} occurrences</li>")

    lines.extend([
        "</ul>",
        "<h2>API Latency</h2>",
        "<table border='1'>",
        "<tr><th>Endpoint</th><th>Avg (ms)</th></tr>",
    ])

    for endpoint, durations in metrics.api_latency.items():
        avg_ms = sum(durations) / len(durations)
        lines.append(f"<tr><td>{endpoint}</td><td>{round(avg_ms, 1)}</td></tr>")

    lines.extend([
        "</table>",
        "<h2>Active Sessions</h2>",
        f"<p>{len(metrics.active_sessions)} user(s) currently active</p>",
        "</body>",
        "</html>",
    ])

    with open(output_path, "w") as f:
        f.write("\n".join(lines))


# ============================================================================
# Main Pipeline
# ============================================================================

def run_pipeline() -> None:
    """Execute the full ETL pipeline: extract, transform, load, and report."""
    config = Config.from_env()

    # Extract
    entries = extract_log_entries(config.log_file)

    # Transform
    metrics = transform_entries(entries)

    # Load
    load_metrics_to_db(metrics, config.db_path, config)

    # Report
    generate_html_report(metrics, "report.html")

    print(f"Job finished at {datetime.now()}")


def create_sample_log_file(log_file: str) -> None:
    """Create a sample log file for testing if it doesn't exist."""
    if not os.path.exists(log_file):
        with open(log_file, "w") as f:
            f.write("2024-01-01 12:00:00 INFO User 42 logged in\n")
            f.write("2024-01-01 12:05:00 ERROR Database timeout\n")
            f.write("2024-01-01 12:05:05 ERROR Database timeout\n")
            f.write("2024-01-01 12:08:00 INFO API /users/profile took 250ms\n")
            f.write("2024-01-01 12:09:00 WARN Memory usage at 87%\n")
            f.write("2024-01-01 12:10:00 INFO User 42 logged out\n")


if __name__ == "__main__":
    config = Config.from_env()
    create_sample_log_file(config.log_file)
    run_pipeline()