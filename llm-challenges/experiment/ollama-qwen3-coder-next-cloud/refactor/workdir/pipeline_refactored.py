"""Pipeline script for processing server logs and generating a report.

This module implements an ETL (Extract, Transform, Load) pattern for
processing server logs, storing metrics in a database, and generating
an HTML report.

All configuration is done via environment variables:

- LOG_FILE: Path to the server log file (default: "server.log")
- DB_PATH: Path to the SQLite database file (default: "metrics.db")
- REPORT_PATH: Path to the output HTML report (default: "report.html")
"""

from __future__ import annotations

import datetime
import os
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import dotenv


@dataclass(frozen=True, slots=True)
class ErrorRecord:
    """Represents an error entry from log parsing."""

    datetime: str
    message: str


@dataclass(frozen=True, slots=True)
class UserRecord:
    """Represents a user action entry from log parsing."""

    datetime: str
    user_id: str
    action: str


@dataclass(frozen=True, slots=True)
class ApiCallRecord:
    """Represents an API call entry from log parsing."""

    datetime: str
    endpoint: str
    latency_ms: int


@dataclass(frozen=True, slots=True)
class Config:
    """Configuration loaded from environment variables."""

    log_file: Path
    db_path: Path
    report_path: Path

    @classmethod
    def from_env(cls) -> Config:
        """Load configuration from environment variables."""
        dotenv.load_dotenv()

        return cls(
            log_file=Path(os.getenv("LOG_FILE", "server.log")),
            db_path=Path(os.getenv("DB_PATH", "metrics.db")),
            report_path=Path(os.getenv("REPORT_PATH", "report.html")),
        )


# ============================================================================
# EXTRACT: Log Parsing
# ============================================================================


def parse_log_file(log_path: Path) -> tuple[list[ErrorRecord], list[UserRecord], list[ApiCallRecord]]:
    """Parse a server log file and extract structured records.

    Uses regex patterns to reliably extract fields from log lines.

    Log line formats:
        ERROR <datetime> <message>
        INFO <datetime> User <uid> <action>
        INFO <datetime> API <endpoint> took <ms>ms
        WARN <datetime> <message>

    Args:
        log_path: Path to the server log file.

    Returns:
        A tuple of (errors, users, api_calls) lists.
    """
    if not log_path.exists():
        return [], [], []

    errors: list[ErrorRecord] = []
    users: list[UserRecord] = []
    api_calls: list[ApiCallRecord] = []

    # Regex patterns for parsing log lines
    error_pattern = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) ERROR (.*)$")
    user_pattern = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) INFO User (\d+) (.*)$")
    api_pattern = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) INFO API (\S+) took (\d+)ms$")
    warn_pattern = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) WARN (.*)$")

    with open(log_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if not line:
                continue

            if match := error_pattern.match(line):
                dt, msg = match.groups()
                errors.append(ErrorRecord(datetime=dt, message=msg))
            elif match := user_pattern.match(line):
                dt, uid, action = match.groups()
                users.append(UserRecord(datetime=dt, user_id=uid, action=action))
            elif match := api_pattern.match(line):
                dt, endpoint, latency = match.groups()
                api_calls.append(ApiCallRecord(datetime=dt, endpoint=endpoint, latency_ms=int(latency)))
            elif match := warn_pattern.match(line):
                # WARN lines are logged but not stored in structured form
                # They could be added to an ErrorRecord if needed
                pass

    return errors, users, api_calls


def build_user_sessions(users: list[UserRecord]) -> dict[str, str]:
    """Build a mapping of active user sessions from login/logout events.

    Args:
        users: List of user action records.

    Returns:
        Dict mapping user_id to login datetime for currently active sessions.
    """
    sessions: dict[str, str] = {}

    for user in users:
        if "logged in" in user.action:
            sessions[user.user_id] = user.datetime
        elif "logged out" in user.action and user.user_id in sessions:
            del sessions[user.user_id]

    return sessions


# ============================================================================
# TRANSFORM: Data Aggregation
# ============================================================================


def aggregate_errors(errors: list[ErrorRecord]) -> dict[str, int]:
    """Count occurrences of each error message.

    Args:
        errors: List of error records.

    Returns:
        Dict mapping error message to occurrence count.
    """
    counts: dict[str, int] = {}
    for error in errors:
        counts[error.message] = counts.get(error.message, 0) + 1
    return counts


def aggregate_api_metrics(api_calls: list[ApiCallRecord]) -> dict[str, float]:
    """Compute average latency per API endpoint.

    Args:
        api_calls: List of API call records.

    Returns:
        Dict mapping endpoint to average latency in ms.
    """
    endpoint_times: dict[str, list[int]] = {}
    for call in api_calls:
        endpoint_times.setdefault(call.endpoint, []).append(call.latency_ms)

    return {endpoint: sum(times) / len(times) for endpoint, times in endpoint_times.items()}


# ============================================================================
# LOAD: Database Operations
# ============================================================================


def init_database(db_path: Path) -> sqlite3.Connection:
    """Initialize the database schema.

    Args:
        db_path: Path to the SQLite database file.

    Returns:
        Open database connection.
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(
        "CREATE TABLE IF NOT EXISTS errors (dt TEXT, message TEXT, count INTEGER)"
    )
    cursor.execute(
        "CREATE TABLE IF NOT EXISTS api_metrics (dt TEXT, endpoint TEXT, avg_ms REAL)"
    )
    conn.commit()
    return conn


def store_errors(conn: sqlite3.Connection, error_counts: dict[str, int]) -> None:
    """Store error aggregation in the database using parameterized queries.

    Args:
        conn: Open database connection.
        error_counts: Dict mapping error message to count.
    """
    cursor = conn.cursor()
    now = datetime.datetime.now().isoformat()

    for message, count in error_counts.items():
        # Parameterized query - safe from SQL injection
        cursor.execute(
            "INSERT INTO errors (dt, message, count) VALUES (?, ?, ?)",
            (now, message, count),
        )

    conn.commit()


def store_api_metrics(conn: sqlite3.Connection, api_metrics: dict[str, float]) -> None:
    """Store API latency metrics in the database using parameterized queries.

    Args:
        conn: Open database connection.
        api_metrics: Dict mapping endpoint to average latency.
    """
    cursor = conn.cursor()
    now = datetime.datetime.now().isoformat()

    for endpoint, avg_ms in api_metrics.items():
        # Parameterized query - safe from SQL injection
        cursor.execute(
            "INSERT INTO api_metrics (dt, endpoint, avg_ms) VALUES (?, ?, ?)",
            (now, endpoint, avg_ms),
        )

    conn.commit()


def close_database(conn: sqlite3.Connection) -> None:
    """Close the database connection."""
    conn.close()


# ============================================================================
# REPORT GENERATION
# ============================================================================


def generate_html_report(
    error_counts: dict[str, int],
    api_metrics: dict[str, float],
    active_sessions: int,
) -> str:
    """Generate an HTML report with error summary, latency table, and session count.

    Args:
        error_counts: Dict mapping error message to count.
        api_metrics: Dict mapping endpoint to average latency.
        active_sessions: Number of currently active user sessions.

    Returns:
        HTML report as a string.
    """
    lines = [
        "<html>",
        "<head><title>System Report</title></head>",
        "<body>",
    ]

    # Error Summary
    lines.append("<h1>Error Summary</h1>")
    lines.append("<ul>")
    for msg, count in error_counts.items():
        lines.append(f"<li><b>{msg}</b>: {count} occurrences</li>")
    lines.append("</ul>")

    # API Latency
    lines.append("<h2>API Latency</h2>")
    lines.append("<table border='1'>")
    lines.append("<tr><th>Endpoint</th><th>Avg (ms)</th></tr>")
    for endpoint, avg in api_metrics.items():
        lines.append(f"<tr><td>{endpoint}</td><td>{round(avg, 1)}</td></tr>")
    lines.append("</table>")

    # Active Sessions
    lines.append("<h2>Active Sessions</h2>")
    lines.append(f"<p>{active_sessions} user(s) currently active</p>")

    lines.extend(["</body>", "</html>"])

    return "\n".join(lines)


def write_report(report_path: Path, content: str) -> None:
    """Write the HTML report to a file.

    Args:
        report_path: Path to write the report.
        content: HTML report content.
    """
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(content)


# ============================================================================
# MAIN PIPELINE
# ============================================================================


def run_pipeline(config: Optional[Config] = None) -> None:
    """Run the full ETL pipeline.

    This function orchestrates the Extract, Transform, and Load phases
    to process server logs and generate a report.

    Args:
        config: Optional config override. If None, loads from environment.
    """
    if config is None:
        config = Config.from_env()

    # Extract phase: Parse log file
    errors, users, api_calls = parse_log_file(config.log_file)

    # Transform phase: Aggregate data
    error_counts = aggregate_errors(errors)
    api_metrics = aggregate_api_metrics(api_calls)
    sessions = build_user_sessions(users)

    # Load phase: Store in database
    conn = init_database(config.db_path)
    try:
        store_errors(conn, error_counts)
        store_api_metrics(conn, api_metrics)
    finally:
        close_database(conn)

    # Generate report
    report_content = generate_html_report(
        error_counts=error_counts,
        api_metrics=api_metrics,
        active_sessions=len(sessions),
    )
    write_report(config.report_path, report_content)

    print(f"Job finished at {datetime.datetime.now().isoformat()}")


if __name__ == "__main__":
    # Create a default log file if none exists (for testing)
    config = Config.from_env()
    if not config.log_file.exists():
        config.log_file.parent.mkdir(parents=True, exist_ok=True)
        with open(config.log_file, "w", encoding="utf-8") as f:
            f.write("2024-01-01 12:00:00 INFO User 42 logged in\n")
            f.write("2024-01-01 12:05:00 ERROR Database timeout\n")
            f.write("2024-01-01 12:05:05 ERROR Database timeout\n")
            f.write("2024-01-01 12:08:00 INFO API /users/profile took 250ms\n")
            f.write("2024-01-01 12:09:00 WARN Memory usage at 87%\n")
            f.write("2024-01-01 12:10:00 INFO User 42 logged out\n")

    run_pipeline()
