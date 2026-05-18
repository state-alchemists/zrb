"""Log processing pipeline with Extract, Transform, Load pattern.

This script processes server logs and generates an HTML report with:
- Error summary with occurrence counts
- API latency metrics per endpoint
- Active user sessions count

Configuration is loaded from environment variables. Uses parameterized
SQL queries to prevent injection vulnerabilities.
"""

import os
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List

import sqlite3


@dataclass
class LogEntry:
    """Represents a parsed log entry."""
    timestamp: str
    level: str
    message: str
    user_id: str | None = None
    action: str | None = None
    endpoint: str | None = None
    duration_ms: int | None = None


@dataclass
class ErrorSummary:
    """Error message with occurrence count."""
    message: str
    count: int


@dataclass
class ApiMetric:
    """API performance metric."""
    endpoint: str
    avg_ms: float


@dataclass
class ReportData:
    """Data needed to generate the HTML report."""
    errors: List[ErrorSummary]
    api_metrics: List[ApiMetric]
    active_sessions: int


class Config:
    """Configuration loaded from environment variables."""

    def __init__(self) -> None:
        """Initialize config from environment variables with defaults."""
        self.db_path: str = os.getenv("DB_PATH", "metrics.db")
        self.log_file: str = os.getenv("LOG_FILE", "server.log")
        self.db_host: str = os.getenv("DB_HOST", "localhost")
        self.db_port: int = int(os.getenv("DB_PORT", "5432"))
        self.db_user: str = os.getenv("DB_USER", "admin")
        self.db_pass: str = os.getenv("DB_PASS", "password")
        self.report_output: str = os.getenv("REPORT_OUTPUT", "report.html")


# Regex patterns for log line parsing
DATETIME_PATTERN = r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})"
LEVEL_PATTERN = r"(ERROR|INFO|WARN)"
USER_PATTERN = r"User (\d+) (.+)"
API_PATTERN = r"API (\S+) took (\d+)ms"
WARNING_PATTERN = r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) WARN (.+)"
ERROR_PATTERN = r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) ERROR (.+)"


def extract_log_data(log_file: str) -> List[LogEntry]:
    """Extract and parse log entries from the log file.

    Args:
        log_file: Path to the log file.

    Returns:
        List of parsed LogEntry objects.
    """
    entries: List[LogEntry] = []

    if not os.path.exists(log_file):
        return entries

    with open(log_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            # Parse timestamp and level
            dt_match = re.match(DATETIME_PATTERN, line)
            lvl_match = re.search(LEVEL_PATTERN, line)

            if not dt_match or not lvl_match:
                continue

            timestamp = dt_match.group(1)
            level = lvl_match.group(1)

            # Parse based on log type
            if level == "ERROR":
                msg = re.search(ERROR_PATTERN, line)
                if msg:
                    entries.append(LogEntry(
                        timestamp=timestamp,
                        level=level,
                        message=msg.group(2)
                    ))

            elif level == "WARN":
                msg = re.search(WARNING_PATTERN, line)
                if msg:
                    entries.append(LogEntry(
                        timestamp=timestamp,
                        level=level,
                        message=msg.group(2)
                    ))

            elif level == "INFO":
                user_match = re.search(USER_PATTERN, line)
                if user_match:
                    entries.append(LogEntry(
                        timestamp=timestamp,
                        level=level,
                        message=f"User {user_match.group(1)} {user_match.group(2)}",
                        user_id=user_match.group(1),
                        action=user_match.group(2)
                    ))
                    continue

                api_match = re.search(API_PATTERN, line)
                if api_match:
                    entries.append(LogEntry(
                        timestamp=timestamp,
                        level=level,
                        message=f"API {api_match.group(1)} took {api_match.group(2)}ms",
                        endpoint=api_match.group(1),
                        duration_ms=int(api_match.group(2))
                    ))

    return entries


def transform_data(entries: List[LogEntry]) -> ReportData:
    """Transform log entries into structured report data.

    Args:
        entries: List of parsed log entries.

    Returns:
        ReportData containing error summaries, API metrics, and active sessions.
    """
    # Track errors
    error_counts: Dict[str, int] = {}
    errors: List[ErrorSummary] = []

    # Track API calls
    endpoint_times: Dict[str, List[int]] = {}
    api_metrics: List[ApiMetric] = []

    # Track active sessions
    sessions: Dict[str, str] = {}

    for entry in entries:
        if entry.level == "ERROR":
            error_counts[entry.message] = error_counts.get(entry.message, 0) + 1

        elif entry.endpoint and entry.duration_ms is not None:
            endpoint_times.setdefault(entry.endpoint, []).append(entry.duration_ms)

        elif entry.user_id and entry.action:
            if "logged in" in entry.action:
                sessions[entry.user_id] = entry.timestamp
            elif "logged out" in entry.action and entry.user_id in sessions:
                del sessions[entry.user_id]

    # Build error summaries
    errors = [
        ErrorSummary(message=msg, count=count)
        for msg, count in error_counts.items()
    ]

    # Build API metrics
    api_metrics = [
        ApiMetric(
            endpoint=endpoint,
            avg_ms=sum(times) / len(times)
        )
        for endpoint, times in endpoint_times.items()
    ]

    return ReportData(
        errors=errors,
        api_metrics=api_metrics,
        active_sessions=len(sessions)
    )


def create_database(db_path: str) -> sqlite3.Connection:
    """Create database schema and return connection.

    Args:
        db_path: Path to the SQLite database file.

    Returns:
        Active database connection.
    """
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

    return conn


def load_data(conn: sqlite3.Connection, data: ReportData) -> None:
    """Load transformed data into the database using parameterized queries.

    Args:
        conn: Active database connection.
        data: ReportData to persist.
    """
    cursor = conn.cursor()
    now = datetime.now().isoformat()

    # Insert error counts with parameterized query
    for error in data.errors:
        cursor.execute(
            "INSERT INTO errors VALUES (?, ?, ?)",
            (now, error.message, error.count)
        )

    # Insert API metrics with parameterized query
    for metric in data.api_metrics:
        cursor.execute(
            "INSERT INTO api_metrics VALUES (?, ?, ?)",
            (now, metric.endpoint, metric.avg_ms)
        )

    conn.commit()


def generate_html_report(data: ReportData, output_path: str) -> None:
    """Generate HTML report from transformed data.

    Args:
        data: ReportData containing metrics.
        output_path: Path where the HTML report will be written.
    """
    html_parts = [
        "<html>\n<head><title>System Report</title></head>\n<body>\n",
        "<h1>Error Summary</h1>\n<ul>\n"
    ]

    for error in data.errors:
        html_parts.append(
            f"<li><b>{error.message}</b>: {error.count} occurrences</li>\n"
        )

    html_parts.append("</ul>\n")
    html_parts.append("<h2>API Latency</h2>\n<table border='1'>\n")
    html_parts.append("<tr><th>Endpoint</th><th>Avg (ms)</th></tr>\n")

    for metric in data.api_metrics:
        html_parts.append(
            f"<tr><td>{metric.endpoint}</td><td>{round(metric.avg_ms, 1)}</td></tr>\n"
        )

    html_parts.append("</table>\n")
    html_parts.append("<h2>Active Sessions</h2>\n")
    html_parts.append(f"<p>{data.active_sessions} user(s) currently active</p>\n")
    html_parts.append("</body>\n</html>")

    html_content = "".join(html_parts)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_content)


def main() -> None:
    """Execute the ETL pipeline."""
    config = Config()

    print(f"Processing log file: {config.log_file}")

    # Extract
    entries = extract_log_data(config.log_file)
    print(f"Parsed {len(entries)} log entries")

    # Transform
    report_data = transform_data(entries)

    # Load - Database
    print(f"Connecting to database: {config.db_path}")
    conn = create_database(config.db_path)
    load_data(conn, report_data)
    conn.close()

    # Load - Report
    generate_html_report(report_data, config.report_output)
    print(f"Report generated: {config.report_output}")
    print(f"Job finished at {datetime.now()}")


if __name__ == "__main__":
    # Create sample log file if it doesn't exist
    if not os.path.exists(os.getenv("LOG_FILE", "server.log")):
        log_path = os.getenv("LOG_FILE", "server.log")
        with open(log_path, "w", encoding="utf-8") as f:
            f.write("2024-01-01 12:00:00 INFO User 42 logged in\n")
            f.write("2024-01-01 12:05:00 ERROR Database timeout\n")
            f.write("2024-01-01 12:05:05 ERROR Database timeout\n")
            f.write("2024-01-01 12:08:00 INFO API /users/profile took 250ms\n")
            f.write("2024-01-01 12:09:00 WARN Memory usage at 87%\n")
            f.write("2024-01-01 12:10:00 INFO User 42 logged out\n")

    main()